#!/bin/sh
# Cyclops variant of the Luckfox RV1106 RkLunch.sh.
# Keeps the vendor module-load, ethernet, and linker setup, but replaces the
# fragile rkipc.ini boot logic with a direct, single camera-owner launch:
# cyclops-eye when configured, otherwise stock rkipc as a fallback.

rcS() {
	for i in /oem/usr/etc/init.d/S??*; do
		[ ! -f "$i" ] && continue
		case "$i" in
		*.sh) ( trap - INT QUIT TSTP; set start; . $i ) ;;
		*) $i start ;;
		esac
	done
}

check_linker() {
	[ ! -L "$2" ] && ln -sf $1 $2
}

network_init() {
	ethaddr1=$(ifconfig -a | grep "eth.*HWaddr" | awk '{print $5}')
	if [ -f /data/ethaddr.txt ]; then
		ethaddr2=$(cat /data/ethaddr.txt)
		if [ "$ethaddr1" = "$ethaddr2" ]; then
			echo "eth HWaddr cfg ok"
		else
			ifconfig eth0 down
			ifconfig eth0 hw ether "$ethaddr2"
		fi
	else
		echo "$ethaddr1" >/data/ethaddr.txt
	fi
	ifconfig eth0 up && udhcpc -i eth0 >/dev/null 2>&1
}

camera_owner() {
	cyclops_conf=
	[ -f /oem/etc/cyclops-eye.conf ] && cyclops_conf=/oem/etc/cyclops-eye.conf
	[ -z "$cyclops_conf" ] && [ -f /etc/cyclops-eye.conf ] && cyclops_conf=/etc/cyclops-eye.conf

	if [ -x /oem/usr/bin/cyclops-eye ] && [ -n "$cyclops_conf" ]; then
		echo "starting cyclops-eye ($cyclops_conf)"
		/oem/usr/bin/cyclops-eye "$cyclops_conf" &
	elif [ -d /oem/usr/share/iqfiles ]; then
		rkipc -a /oem/usr/share/iqfiles &
	else
		rkipc &
	fi
}

post_chk() {
	cnt=0
	while [ "$cnt" -lt 30 ]; do
		cnt=$((cnt + 1))
		mount | grep -w userdata && break
		sleep .1
	done

	default_ko_dir=/ko
	[ -f /oem/usr/ko/insmod_ko.sh ] && default_ko_dir=/oem/usr/ko
	if [ -f "$default_ko_dir/insmod_ko.sh" ]; then
		( cd "$default_ko_dir" && sh insmod_ko.sh )
	fi

	network_init &
	check_linker /userdata /oem/usr/www/userdata
	check_linker /media/usb0 /oem/usr/www/usb0
	check_linker /mnt/sdcard /oem/usr/www/sdcard

	camera_owner
}

rcS

ulimit -c unlimited
echo "/data/core-%p-%e" >/proc/sys/kernel/core_pattern
echo 1 >/proc/sys/vm/overcommit_memory

post_chk &
