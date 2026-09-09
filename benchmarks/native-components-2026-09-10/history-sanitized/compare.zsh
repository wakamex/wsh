module_path=($1 $module_path)
zmodload wshhistory || exit 2
source $2
zmodload zsh/parameter
fc -p
HISTSIZE=1000
unsetopt hist_ignore_all_dups hist_ignore_dups hist_find_no_dups
for text in 'echo older' 'echo older' 'echo newer' $'echo multiline\nnext' 'Echo MIXED' 'echo [x]' 'echo *star' 'echo é' 'other' 'sentinel'; do print -s -- "$text"; done
HISTORY_SUBSTRING_SEARCH_ENSURE_UNIQUE=$3
HISTORY_SUBSTRING_SEARCH_FUZZY=$4
HISTORY_SUBSTRING_SEARCH_PREFIXED=$5
(( $6 )) && setopt hist_find_no_dups
HISTORY_SUBSTRING_SEARCH_GLOBBING_FLAGS=$7
for query in 'echo' 'echo older' 'echo new' '[x]' '*star' 'é' 'absent'; do
 BUFFER=$query
 _history_substring_search_result=''
 for direction in up up up down up up up up up up down down down down down; do
  WIDGET=history-substring-search-$direction
  _history-substring-search-begin
  _history-substring-search-$direction-search
  print -r -- "${(qqqq)BUFFER}:$_history_substring_search_match_index:${(qqqq)_history_substring_search_query_highlight}"
  _history_substring_search_result=$BUFFER
 done
 print -s -- 'echo live history'
 print -s -- 'sentinel'
done
