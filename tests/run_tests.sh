#!/bin/bash

set -e
set -u
set -o pipefail

function error_msg {
	>&2 echo "[ERROR] $@"
}

if [[ ! -x "$( which define )" ]]; then
	error_msg "define is not in PATH - the tests can only be run in a properly set-up TurboMole environment"
	exit 1
fi

if [[ ! -x "$( which python3 )" ]]; then
	error_msg "python3 is not in PATH"
	exit 2
fi

export script_dir="$( realpath "$( dirname "$0" )" )"

function perform_test {
	local input="$( realpath "$1" )"
	local test_name="$( basename "$input" .json )"

	echo "> Running ${test_name}..."

	local expectations="$( dirname "$input" )/${test_name}.grep"
	local script="${script_dir}/../prep_turbomole_calc.py"

	if [[ ! -f "$script" ]]; then
		error_msg "Unable to find script '$script'"
		exit 3
	fi

	local workdir="$script_dir/$test_name"
	if [[ -d "$workdir" ]]; then
		# Clear workdir
		rm -rf "$workdir/"
	fi
	# Create workdir
	mkdir "$workdir"

	cd "$workdir"

	# Execute script
	python3 "$script" "$input"

	local control_file="control"

	if [[ ! -f "$control_file" ]]; then
		error_msg "No control file generated (expected it at '$control_file')"
		exit 4
	fi

	readarray -t lines < "$expectations"
	for current in "${lines[@]}"; do
		search_in="$control_file"
		if [[ "$current" =~ ^(.+)\ in\ (.+)$ ]]; then
			current="${BASH_REMATCH[1]}"
			search_in="${BASH_REMATCH[2]}"
		fi

		if [[ "$current" = !* ]]; then
			# Must NOT find
			# Remove leading exclamation mark
			current="${current:1}"
			if grep "$current" "$search_in" > /dev/null; then
				error_msg "Expected to NOT match '$current' in '$search_in', but did"
			fi
		else
			# Must find
			if ! grep "$current" "$search_in" > /dev/null; then
				error_msg "Expected to match '$current' in '$search_in', but didn't"
			fi
		fi
	done

	echo "< Test $test_name passed"
}

export -f perform_test
export -f error_msg
export SHELLOPTS

find "$script_dir" -maxdepth 1 -type f -iname "*.json" -exec bash -c "perform_test {}" \;
