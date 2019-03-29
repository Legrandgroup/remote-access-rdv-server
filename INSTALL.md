# Introduction

This documentation details a step-by-step procedure to setup a new RDV server.

Installation des paquets nécessaires
Réglage des permissions D-Bus
Installation du logiciel côté serveur RDV
Création de comptes sur le RDV server
Création d'un compte pour un onsite dev
Création d'un compte pour un master dev
Enregistrement du compte dans le framework accès distant
Logs du serveur RDV

# Installation of required packages

```
sudo apt-get install liblzo2-dev libssl-dev bison flex lsof tcpdump openssh-server python-ipaddr bridge-utils
```

# Setting-up of D-Bus permissions

D-Bus is the communication bus (IPC) used between shell instances (*dev_shell.py) and the tunnel management process (vtun_manager.py)

In order for IPC to work properly, a specific D-Bus configuration must be created and stored, for example in a file named `/etc/dbus-1/system.d/vtun_manager.conf`.
You will have to edit it as root and fill-it in with the following content:
```
<!DOCTYPE busconfig PUBLIC
 "-//freedesktop//DTD D-BUS Bus Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>
  <policy context="default">
    <allow own="com.legrandelectric.RemoteAccess.TundevManager"/>
    <allow send_destination="com.legrandelectric.RemoteAccess.TundevManager"/>
  </policy>
</busconfig>
```

# Software installation

Inside `/opt/local`, as root, get a copy of the softare (example below is via git, but we can also unzip a release zip package):
```
mkdir -p /opt/local
cd /opt/local/
git clone https://git.bticino.it/scm/devsmrmtacc/rdv-server-tundev-shell.git
cd rdv-server-tundev-shell/
git clone https://git.bticino.it/scm/devsmrmtacc/pythonvtunlib.git
```

Now, run the server manually just to test:

```
sudo /opt/local/rdv-server-tundev-shell/vtun_manager.py -d
```
If this works, a few more steps below are required in order to run this service at boot time.
For this, you can use the system V init script init provided in the sources. As root:
```
ln -s /opt/local/rdv-server-tundev-shell/init.d/vtunmanager /etc/init.d/vtunmanager
update-rc.d vtunmanager defaults
/etc/init.d/vtunmanager start
```

# Account creation

For each new onsite or master RPI, a new UNIX account is required on the RDV server.
Each new account is uniquely identified by an ID (number), that must not yet be in use (and that will match the UNIX user ID).
The format of a new account is `rpixxxx` with `xxxx` being the unique sequence number, for example: `rpi1100`
On debian, a good practice is to start from 1100, as normal user accounts start from 1000, we thus provision for 100 normal users before Raspberry user accounts.

To list already used UIDs, run the following command on the RDV server:

```
sudo cat /etc/passwd
```

If you followed the above convention, all accounts associated with tunelling devices will have a UID `11xx`, and the corresponding usernames will look like `rpi11xx`.

# Account creation for an onsite dev

On the RDV server, as root:
```
user=1100
adduser --system --no-create-home --uid "${user}" --shell /opt/local/rdv-server-tundev-shell/onsitedev_shell.py --ingroup users rpi"${user}"
mkdir /home/rpi"${user}"
chown "${user}":users /home/rpi"${user}"
```
On this user account, no password-based authentication should be allowed (only public-key authentication).

ssh should now be setup to trust the public key generated on the onsite device (we assume this key is store in the environment variable $KEY).
As root:
```
# KEY="ssh-rsa AAAAB3NzaC1yc2EAAA..."
mkdir -p /home/rpi"${user}"/.ssh
chown "${user}":users /home/rpi"${user}"/.ssh
chmod 700 /home/rpi"${user}"/.ssh
touch /home/rpi"${user}"/.ssh/authorized_keys
chown "${user}":users /home/rpi"${user}"/.ssh/authorized_keys
chmod 644 /home/rpi"${user}"/.ssh/authorized_keys
echo "$KEY" >> /home/rpi"${user}"/.ssh/authorized_keys
```
Test this new key by trying an ssh connection to the RDV server directly from the onsite dev. You should get an onsite tundev shell prompt. Check that the role is master by running the following tundev shell command:
```
get_role
```
This will output *onsite*

For this test to work, you will need a working internet connection on the onsite device, as well as network that allows outgoing SSH connections (TCP port 22) from the onsite dev

Once the UNIX account for the new onsite dev has been created, you will have to enable tunnels from this device by following the procedure below

# Account creation for a master dev

On the RDV server, as root:
```
user=1101
adduser --system --no-create-home --uid "${user}" --shell /opt/local/rdv-server-tundev-shell/masterdev_shell.py --ingroup users rpi"${user}"
mkdir /home/rpi"${user}"
chown "${user}":users /home/rpi"${user}"
```
On this user account, no password-based authentication should be allowed (only public-key authentication).

ssh should now be setup to trust the public key generated on the onsite device (we assume this key is store in the environment variable $KEY).
As root:
```
# KEY="ssh-rsa AAAAB3NzaC1yc2EAAA..."
mkdir -p /home/rpi"${user}"/.ssh
chown "${user}":users /home/rpi"${user}"/.ssh
chmod 700 /home/rpi"${user}"/.ssh
touch /home/rpi"${user}"/.ssh/authorized_keys
chown "${user}":users /home/rpi"${user}"/.ssh/authorized_keys
chmod 644 /home/rpi"${user}"/.ssh/authorized_keys
echo "$KEY" >> /home/rpi"${user}"/.ssh/authorized_keys
```
Test this new key by trying an ssh connection to the RDV server directly from the onsite dev. You should get a master tundev shell prompt. Check that the role is master by running the following tundev shell command:
```
get_role
```
This will output *master*

For this test to work, you will need a working internet connection on the master device, as well as network that allows outgoing SSH connections (TCP port 22) from the master dev

Once the UNIX account for the new master dev has been created, you will have to enable tunnels from this device by following the procedure below

# RDV server logs

Whenever the RDV python script is run at boot time (from init), the script runs as daemon (without the debug option `-d`).
In such cases, all logs (usually printed on the console when using `-d`) will instead be stored in a file called `/var/log/vtun_manager.log`