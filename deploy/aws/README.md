# Deploy on one free-tier EC2 instance

One `t3.micro` (or `t2.micro`) in `ap-southeast-1`, about 1 GB RAM. The instance
installs a 1 GB swapfile, clones
`https://github.com/endenko/CaculateGradeUED` branch
`feature/vietocr-all-faculties-ued-ui`, and serves the light OCR build
(`OCR_LIGHT=1`, Python 3.12) with gunicorn behind port 80.

`deploy/aws/Dockerfile` is the image to use. The Dockerfile at the repo root
installs VietOCR and is too large for this instance. The container is started
with `--restart=always`. If Docker cannot start, `user-data.sh` falls back to a
virtualenv and a systemd unit with `Restart=always`.

The first boot installs packages and builds the image. That takes several
minutes. Then `http://<public-ip>/health` should return `"queue_worker": true`.

## CloudShell

Open AWS CloudShell in **Asia Pacific (Singapore) / ap-southeast-1**, then paste
this. It opens ports 80 and 22, launches Ubuntu 24.04 with the bootstrap script,
allocates an Elastic IP, and prints that IP.

```bash
set -euo pipefail
REGION=ap-southeast-1
git clone --branch feature/vietocr-all-faculties-ued-ui --depth 1 \
  https://github.com/endenko/CaculateGradeUED
cd CaculateGradeUED

SG_ID=$(aws ec2 create-security-group \
  --group-name ued-grade-web \
  --description "UED grade calculator HTTP and SSH" \
  --region "$REGION" \
  --query GroupId --output text)
aws ec2 authorize-security-group-ingress \
  --group-id "$SG_ID" --protocol tcp --port 80 --cidr 0.0.0.0/0 --region "$REGION"
aws ec2 authorize-security-group-ingress \
  --group-id "$SG_ID" --protocol tcp --port 22 --cidr 0.0.0.0/0 --region "$REGION"

AMI=$(aws ssm get-parameter \
  --name /aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id \
  --region "$REGION" --query Parameter.Value --output text)

INSTANCE=$(aws ec2 run-instances \
  --image-id "$AMI" \
  --instance-type t3.micro \
  --region "$REGION" \
  --security-group-ids "$SG_ID" \
  --user-data file://deploy/aws/user-data.sh \
  --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":20,"VolumeType":"gp3","DeleteOnTermination":true}}]' \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=ued-grade}]' \
  --query 'Instances[0].InstanceId' --output text)
echo "instance $INSTANCE"

aws ec2 wait instance-running --instance-ids "$INSTANCE" --region "$REGION"
ALLOC=$(aws ec2 allocate-address --domain vpc --region "$REGION" --query AllocationId --output text)
aws ec2 associate-address --instance-id "$INSTANCE" --allocation-id "$ALLOC" --region "$REGION"
aws ec2 describe-addresses --allocation-ids "$ALLOC" --region "$REGION" \
  --query 'Addresses[0].PublicIp' --output text
```

Use `t2.micro` instead of `t3.micro` if that is the instance type on the account's
free tier. Amazon Linux 2023 works with the same user-data; replace the AMI line
with:

```bash
AMI=$(aws ssm get-parameter \
  --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 \
  --region "$REGION" --query Parameter.Value --output text)
```

and set the root device to `/dev/xvda` in `--block-device-mappings`.

Port 22 is open so you can read `/var/log/ued-bootstrap.log`. Add
`--key-name YOUR_KEY` to `run-instances` first, and prefer limiting port 22 to
your own IP. The app itself does not need SSH.

The commands assume the default VPC. If `run-instances` says there is no
default subnet, create a subnet in a VPC that has an internet gateway and pass
`--subnet-id` plus `--associate-public-ip-address`.

An Elastic IP is free while it is attached to a running instance. Release it
when you terminate the instance:

```bash
aws ec2 release-address --allocation-id "$ALLOC" --region "$REGION"
aws ec2 terminate-instances --instance-ids "$INSTANCE" --region "$REGION"
```

## Google Calendar OAuth

The Lịch tab always offers a one-off Google event link and a private `.ics` feed. The “Đồng bộ Google (OAuth)” button stays hidden until both variables exist on the instance:

```bash
GOOGLE_CLIENT_ID=....apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=...
```

In Google Cloud Console, create an OAuth client of type Web application. Add the authorized redirect URI `http://YOUR_PUBLIC_IP/api/calendar/google/callback` (or `https://` if you terminate TLS). The scope used is `https://www.googleapis.com/auth/calendar.events`. Put the two variables in the instance environment and restart the container. Without them, nothing calls Google.
