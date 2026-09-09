module_path=($1 $module_path)
zmodload wshdirectory || exit 2
source $2
shift 2
ZSHZ_CASE=$1 ZSHZ_TRAILING_SLASH=$2 ZSHZ_UNCOMMON=$3
[[ $4 == keep ]] && ZSHZ_KEEP_DIRS=($HOME/missing)
shift 4
zshz "$@"
result=$?
print -r -- "WSH_RESULT:$result"
