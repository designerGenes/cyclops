#!/bin/sh
# Cyclops variant of the vendor RkLunch-stop.sh.
#
# The vendor script stops rkipc + udhcpc. We additionally HARD-kill the Cyclops
# camera owner: a clean SIGTERM makes cyclops-eye run its rk_aiq
# stop/deinit teardown, which SIGSEGVs inside librkaiq (the core-*-cyclops-eye
# dumps) and can leave the ISP/MPP media block wedged. SIGKILL skips that
# buggy teardown entirely; the reboot resets the media block anyway.

rcK()
{
	for i in $(ls /oem/usr/etc/init.d/S??*) ;do
		[ ! -f "$i" ] && continue
		case "$i" in
			*.sh)
				( trap - INT QUIT TSTP; set stop; . $i )
				;;
			*)
				$i stop
				;;
		esac
	done
}

echo "Stop Application ..."
killall -9 cyclops-eye
killall rkipc
killall udhcpc

while [ 1 ];
do
	sleep 1
	ps|grep rkipc|grep -v grep
	if [ $? -ne 0 ]; then
		echo "rkipc exit"
		break
	else
		echo "rkipc active"
	fi
done

rcK
