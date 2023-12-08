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

script_dir="$( realpath "$( dirname "$0" )" )"
prep_script="$( realpath "${script_dir}/../prep_turbomole_calc.py" )"

if [[ ! -f "$prep_script" ]]; then
	error_msg "Unable to find script '$prep_script'"
	exit 3
fi


function perform_test {
	local input="$1"
	local expectations="$2"

	# Execute script
	python3 "$prep_script" "$input" || exit "$?"

	local control_file="control"

	if [[ ! -f "$control_file" ]]; then
		error_msg "No control file generated"
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
				exit 5
			fi
		else
			# Must find
			if ! grep "$current" "$search_in" > /dev/null; then
				error_msg "Expected to match '$current' in '$search_in', but didn't"
				exit 5
			fi
		fi
	done
}

# See https://stackoverflow.com/a/29779745
function indent {
	 sed 's/^/    /'
}

if [[ -z "${1-}" ]]; then
	readarray -t test_inputs < <( find "$script_dir" -maxdepth 1 -mindepth 1 -type f -iname "*.json" | sort )
else
	declare -a test_inputs=( "$@" )
fi

declare -a passed=()
declare -a failed=()

for current in "${test_inputs[@]}"; do
	test_name="$( basename "$current" .json )"
	work_dir="${script_dir}/${test_name}"

	if [[ -d "$work_dir" ]]; then
		rm -r "$work_dir"
	fi

	mkdir "$work_dir"
	cd "$work_dir"

	echo -n "Running test $test_name..."

	exit_code=0
	test_output="$( 2>&1 perform_test "${script_dir}/${test_name}.json" "${script_dir}/${test_name}.grep" | indent )" || exit_code=$?

	if [[ "$exit_code" -eq 0 ]]; then
		echo " Passed."
		passed+=( "$test_name" )
	else
		echo " ***Failed:"
		echo "$test_output"
		failed+=( "$test_name" )
	fi

	cd "$script_dir"
done

exit_code=0

echo ""

if [[ "${#failed[@]}" -gt 0 ]]; then
	echo "The following tests failed"

	for current in "${failed[@]}"; do
		echo " * $current"
	done

	echo ""

	exit_code=128
fi

echo "${#passed[@]} of $(( ${#passed[@]} + ${#failed[@]} )) tests passed"
exit "$exit_code"
