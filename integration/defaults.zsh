# General interactive defaults, applied before user startup files so their settings win.
setopt always_to_end complete_in_word interactive_comments long_list_jobs prompt_subst
setopt hist_expire_dups_first hist_ignore_dups hist_ignore_space hist_verify
unsetopt flow_control
# Word motions and deletions stop at punctuation such as / and -.
WORDCHARS=
(( ${+PAGER} )) || export PAGER=less
# The fg, bg and related colour arrays, as the colors function sets them.
source ${WSH_BUNDLE_ROOT}/share/wsh/colors.zsh
autoload -Uz colors

() {
  zmodload zsh/terminfo 2>/dev/null
  autoload -Uz edit-command-line up-line-or-beginning-search down-line-or-beginning-search
  zle -N edit-command-line
  zle -N up-line-or-beginning-search
  zle -N down-line-or-beginning-search
  # Terminals send the terminfo sequences only in keypad-transmit mode, which Zsh leaves off,
  # so bind the sequences of both modes.
  local -A keys=(
    $'\e[H' beginning-of-line $'\eOH' beginning-of-line $'\e[1~' beginning-of-line
    $'\e[F' end-of-line $'\eOF' end-of-line $'\e[4~' end-of-line
    $'\e[3~' delete-char $'\e[3;5~' kill-word
    $'\e[1;5C' forward-word $'\e[1;5D' backward-word
    $'\e[5~' up-line-or-history $'\e[6~' down-line-or-history
    $'\e[Z' reverse-menu-complete
    '^?' backward-delete-char '^X^E' edit-command-line
  )
  local capability keymap sequence widget
  for capability widget in khome beginning-of-line kend end-of-line kdch1 delete-char \
      kpp up-line-or-history knp down-line-or-history kcbt reverse-menu-complete; do
    [[ -n ${terminfo[$capability]:-} ]] && keys[$terminfo[$capability]]=$widget
  done
  for keymap in emacs viins vicmd; do
    for sequence widget in ${(kv)keys}; do
      bindkey -M $keymap -- $sequence $widget
    done
  done
  # Space expands history references such as !! in place.
  bindkey -M emacs ' ' magic-space
  bindkey -M viins ' ' magic-space
}

# The menu and matching styles use the general context, so the same style in a user file replaces them.
zstyle ':completion:*' menu select
zstyle ':completion:*' matcher-list 'm:{[:lower:][:upper:]}={[:upper:][:lower:]}'
zstyle -e ':completion:*' list-colors 'reply=(${(s.:.)${LS_COLORS:-di=01;34:ln=01;36:so=01;35:pi=33:ex=01;32:bd=01;33:cd=01;33}})'
zstyle ':completion:*:*:kill:*:processes' list-colors '=(#b) #([0-9]#) ([0-9a-z-]#)*=01;34=0=01'
zstyle ':completion:*:*:*:*:processes' command "ps -u $USERNAME -o pid,user,comm -w -w"
zstyle ':completion:*:cd:*' tag-order local-directories directory-stack path-directories
zstyle ':completion:*:*:*:users' ignored-patterns \
  adm amanda apache at avahi avahi-autoipd beaglidx bin cacti canna clamav daemon dbus distcache \
  dnsmasq dovecot fax ftp games gdm gkrellmd gopher hacluster haldaemon halt hsqldb ident \
  junkbust kdm ldap lp mail mailman mailnull man messagebus mldonkey mysql nagios named netdump \
  news nfsnobody nobody nscd ntp nut nx obsrun openvpn operator pcap polkitd postfix postgres \
  privoxy pulse pvm quagga radvd rpc rpcuser rpm rtkit scard shutdown squid sshd statd svn sync \
  tftp usbmux uucp vcsa wwwrun xfs '_*'
zstyle '*' single-ignored show

# Startup files call compdef before completion is initialized; keep the calls for later.
typeset -ga _wsh_compdef_queue
compdef() { _wsh_compdef_queue+=("${(j: :)${(@q)@}}") }
