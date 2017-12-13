#!/usr/bin/env bash

set -ex

environment='LOCAL'
project=''
while getopts ":e:p:" opt; do
  case ${opt} in
    e)
      environment="$OPTARG"
      ;;
    p)
      project="$OPTARG"
      ;;
    h)
      usage
      exit 0
      ;;
    \*)
      echo "invalid option"
      exit 1
      ;;
  esac
done

scriptdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
base=$(basename ${scriptdir})
parentdir="$(dirname ${scriptdir})"

# project (the directory where the code is located) defaults to $base
if [ "${project}" == '' ]; then
    project="$base"
fi

# parent directory of common, rhc, test_util
gitdir=''

if [ "${environment}" == "CODEBUILD" ]; then
    gitdir="${base}/git/"
fi

if [ "${base}" == 'common' ] || [ "${base}" == 'rhc' ] || [ "${base}" == 'test_util' ]; then
    export PYTHONPATH="${parentdir}/common:${parentdir}/rhc:${parentdir}/test_util:${PYTHONPATH}"
else
    export PYTHONPATH="${parentdir}/${base}:${parentdir}/${gitdir}rhc:${parentdir}/${gitdir}common:${parentdir}/${gitdir}test_util:${PYTHONPATH}"
fi
echo "${PYTHONPATH}"

#if [ ${#*} == 0 ]
#then
#    pytest "${scriptdir}/tests" -vv --cov "${project}"
#else
#    pytest "${scriptdir}/tests" -vv --cov "${project}" $*
##    pytest "${scriptdir}/tests" -vv --cov $*
#fi

pytest "${scriptdir}/tests" -vv --cov "${project}"