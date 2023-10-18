#!/bin/bash
# Build HTML pages from source

# Script boilerplate
[[ "${BASH_SOURCE[0]}" != "${0}" ]] && my_dir=$(dirname ${BASH_SOURCE[0]}) || my_dir=$(dirname $0)  # Determine script dir even when sourcing

common_dir=$my_dir
. $common_dir/00_common_bash.sh

old_bash_state="$(get_bash_state "$old_bash_state")"
set -xeuf -o pipefail # Set default script debugging flags

###############
# Script body #
###############
echo "80_build_docs packages"
$PIP freeze

# Use the sphinx matching the venv we are in using SPHINXBUILD
VENV_SPHINX_BUILD='../venv_imaspy/bin/sphinx-build'
# Instruct sphinx to treat all warnings as errors
export SPHINXOPTS='-W --keep-going'
make -C docs html SPHINXBUILD="$PYTHON $VENV_SPHINX_BUILD"
