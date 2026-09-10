#!/usr/bin/env python3
"""Run the existing controller comparisons through actual installed startup."""
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
bundle, output = [Path(p).resolve() for p in sys.argv[1:3]]
mode = sys.argv[3]
fixture = output / 'fixture'
fixture.mkdir(parents=True, exist_ok=True)
(fixture / 'control.zsh').write_bytes((bundle / 'share/wsh/defaults/zsh-autosuggestions.zsh').read_bytes())
base = (root / 'native/test-autosuggestions-owner.py').read_text()
base = base.replace('zmodload wshsuggest\nsource $WSH_TEST_SOURCE', '[[ $WSH_TEST_OWNER == control ]] && source $WSH_TEST_SOURCE')
base = base.replace("WSH_DISABLE_AUTOSUGGESTIONS='1',", "WSH_DISABLE_AUTOSUGGESTIONS='0' if owner=='candidate' else '1',WSH_TEST_OWNER=owner,WSH_AUTOSUGGEST_ASYNC='0' if mode in ('sync','completion-sync') else '1',")
if mode in ('correctness', 'measure'):
    source = (root / 'native/test-autosuggestions-complete.py').read_text() if mode == 'correctness' else base
elif mode in ('lifecycle', 'bounds'):
    source = (root / ('native/test-autosuggestions-' + mode + '.py')).read_text()
else:
    raise SystemExit('correctness, measure, lifecycle or bounds')
source = source.replace("(root/'native/test-autosuggestions-owner.py').read_text()", repr(base))
sys.argv = [str(root / 'native/test-installed-autosuggestions.py'), str(bundle / 'bin/wsh'), 'installed', str(fixture), str(output), 'measure' if mode == 'measure' else 'correctness'] + sys.argv[4:]
exec(compile(source, str(root / 'native/test-installed-autosuggestions.py'), 'exec'), {'__file__': str(root / 'native/test-installed-autosuggestions.py'), '__name__': '__main__'})
