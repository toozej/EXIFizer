#!/usr/bin/env bash

set -Eeuo pipefail

if ! command -v python3; then
    echo "Python3 not installed, exiting"
    exit 1
fi

OLD_PYTHON_VERSION="3.12"
NEW_PYTHON_VERSION="${1}"
GIT_REPO_ROOT=$(git rev-parse --show-toplevel)
FILES_NEEDING_UPDATES="${GIT_REPO_ROOT}/Dockerfile* ${GIT_REPO_ROOT}/README.md ${GIT_REPO_ROOT}/scripts/update_python_version.sh ${GIT_REPO_ROOT}/.github/workflows/*"

# rename from $OLD_PYTHON_VERSION to $NEW_PYTHON_VERSION
# shellcheck disable=SC2116,SC2046
grep -rl "${OLD_PYTHON_VERSION}" $(echo "${FILES_NEEDING_UPDATES}") | xargs sed -i "" -e "s/${OLD_PYTHON_VERSION}/${NEW_PYTHON_VERSION}/g"

# show diff output so user can verify their changes
git diff
