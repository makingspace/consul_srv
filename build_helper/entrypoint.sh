#!/usr/bin/dumb-init /bin/bash
# ----------------------------------------------------------------------------
# entrypoint for container
# ----------------------------------------------------------------------------
set -e

HOST_IP=`/bin/grep $HOSTNAME /etc/hosts | /usr/bin/cut -f1`
export HOST_IP=${HOST_IP}
echo
echo "container started with ip: ${HOST_IP}..."
echo
for script in /container-init.d/*; do
	case "$script" in
		*.sh)     echo "... running $script"; . "$script" ;;
		*)        echo "... ignoring $script" ;;
	esac
	echo
done

if [ "$1" == "shell" ]; then
	echo "starting /usr/local/bin/pipenv shell..."
	/usr/local/bin/pipenv shell
else
	echo "Running something else ($@)"
	exec "$@"
fi