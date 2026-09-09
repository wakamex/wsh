module_path=($1 $module_path)
zmodload wshdirectory || exit 2
ZSHZ_CMD=jump
source $2
zshz --add "$HOME/project space" || exit 3
zshz --add "$HOME/project space" || exit 4
jump space || exit 5
[[ $PWD == "$HOME/project space" ]] || exit 6
[[ ${#${(M)chpwd_functions:#_zshz_chpwd}} == 1 ]] || exit 7
print -r -- "WSH_JUMP:$PWD"
