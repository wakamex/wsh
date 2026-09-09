module_path=($1 $module_path)
zmodload wshdirectory || exit 90
source $2
shift 2
local_setup=$1
shift
 eval "$local_setup"
zshz "$@"
result=$?
print -r -- "STATUS:$result"
