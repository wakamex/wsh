#!/usr/bin/env python3
"""Build two unsigned prototype installations from identical configured Zsh sources."""
import gzip,hashlib,json,os,pathlib,shutil,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[2]
OUT=pathlib.Path(__file__).resolve().parent
WORK=pathlib.Path('/var/tmp/wsh-native-entry-prototype')
SOURCE=WORK/'source'
TEMPLATE=ROOT/'bundles/ccf3c17708aae1b1fc23c4170d54ff6e78a919f0adc0e0950f3590c6325c9698'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def run(args,**kw):
    print('+ '+repr([str(a) for a in args]),flush=True)
    subprocess.run([str(a) for a in args],check=True,**kw)
def manifest(directory,native):
    WORK.chmod(0o755)
    directory.chmod(0o755)
    m=json.loads((TEMPLATE/'manifest.json').read_text())
    m['release_id']='development-native-entrypoint-'+('native' if native else 'launcher')
    m['zsh']['configure_args']=['--prefix='+str(WORK/'install/usr'),'--enable-cap','--enable-multibyte','--enable-pcre']
    if native: m['zsh']['patches'].append(sha(OUT/'native-entrypoint.patch'))
    m['files']=[]
    for p in sorted(directory.rglob('*')):
        if not p.is_file() or p.name=='manifest.json': continue
        assert not p.is_symlink(),p
        m['files'].append({'path':str(p.relative_to(directory)),'kind':'file','mode':p.stat().st_mode&0o777,'size':p.stat().st_size,'sha256':sha(p)})
    (directory/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    with gzip.open(OUT/(directory.name+'-manifest.json.gz'),'wb') as f:
        f.write((directory/'manifest.json').read_bytes())
    run([ROOT/'target/release/wsh','bundle','verify',directory])

def main():
    mode=sys.argv[1]
    env=dict(os.environ,LC_ALL='C.UTF-8',LANG='C.UTF-8',TZ='UTC')
    if mode=='control':
        lock=json.loads((ROOT/'build/zsh-sources/zsh-cad0d67c.json').read_text())
        archive=ROOT/'build/cache'/lock['archive_name']
        assert sha(archive)==lock['archive_sha256']
        if SOURCE.exists(): shutil.rmtree(SOURCE)
        SOURCE.mkdir(parents=True)
        if (WORK/'install').exists(): shutil.rmtree(WORK/'install')
        run(['tar','-xf',archive,'-C',SOURCE,'--strip-components=1'])
        for p in lock['source_patches']+lock['test_patches']:
            assert sha(ROOT/p['path'])==p['sha256']
            with (ROOT/p['path']).open('rb') as f: run(['patch','-p1','--batch'],cwd=SOURCE,stdin=f)
        run(['./Util/preconfig'],cwd=SOURCE,env=env)
        run(['./configure','--prefix='+str(WORK/'install/usr'),'--enable-cap','--enable-multibyte','--enable-pcre'],cwd=SOURCE,env=env)
        run(['make','-j8'],cwd=SOURCE,env=env)
        run(['make','install.bin','install.modules','install.fns','DESTDIR='],cwd=SOURCE,env=env)
    if mode in ('control','assemble-control'):
        directory=WORK/'launcher'
        if directory.exists(): shutil.rmtree(directory)
        shutil.copytree(TEMPLATE,directory)
        shutil.copy2(SOURCE/'Src/zsh',directory/'bin/zsh')
        for subtree in ['lib','share/zsh']:
            shutil.rmtree(directory/subtree)
            shutil.copytree(WORK/'install/usr'/subtree,directory/subtree)
        run(['rustc','--edition=2024','-C','opt-level=3',OUT/'launcher.rs','-o',directory/'bin/wsh'])
        manifest(directory,False)
    elif mode=='native':
        with (OUT/'native-entrypoint.patch').open('rb') as f: run(['patch','-p1','--batch'],cwd=SOURCE,stdin=f)
        run(['make','-j8'],cwd=SOURCE,env=env)
        directory=WORK/'native'
        if directory.exists(): shutil.rmtree(directory)
        shutil.copytree(WORK/'launcher',directory)
        shutil.copy2(SOURCE/'Src/zsh',directory/'bin/zsh')
        shutil.copy2(SOURCE/'Src/zsh',directory/'bin/wsh')
        for name in ['native-before.zsh','native-after.zsh','native-finish.zsh']:
            shutil.copy2(OUT/name,directory/'share/wsh'/name)
        # Native startup no longer needs the four redirecting startup files.
        for p in (directory/'share/wsh/zdotdir').iterdir(): p.unlink()
        manifest(directory,True)
        run(['make','check'],cwd=SOURCE,env=env)
    else: raise ValueError(mode)
if __name__=='__main__': main()
