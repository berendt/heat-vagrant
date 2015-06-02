sudo chsh -s /bin/bash ec2-user
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update
sudo apt-get upgrade -y
sudo apt-get install -y git

if [[ ! -e devstack ]]; then
    git clone https://github.com/openstack-dev/devstack
fi

cat > devstack/local.conf << EOF
[[local|localrc]]

DATABASE_PASSWORD=password
RABBIT_PASSWORD=password
SERVICE_TOKEN=password
SERVICE_PASSWORD=password
ADMIN_PASSWORD=password

disable_service n-net
enable_service q-svc
enable_service q-agt
enable_service q-dhcp
enable_service q-l3
enable_service q-meta
enable_service q-metering
enable_service q-vpn
enable_service q-fwaas
enable_service q-lbaas
EOF

cd devstack
./stack.sh
