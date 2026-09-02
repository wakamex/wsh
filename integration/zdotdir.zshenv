if [[ -n ${WSH_BUNDLE_ROOT:-} ]]; then
  module_path=("${WSH_BUNDLE_ROOT}/lib/zsh/5.9.2")
  fpath=("${WSH_BUNDLE_ROOT}/share/zsh/5.9.2/functions")
fi
