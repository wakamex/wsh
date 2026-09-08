fn main() {
    println!("cargo:rerun-if-changed=../../native/git.c");
    println!("cargo:rerun-if-changed=../../native/git.h");
    if std::env::var_os("CARGO_FEATURE_NATIVE_GIT").is_some() {
        cc::Build::new()
            .file("../../native/git.c")
            .flag("-std=c11")
            .warnings(true)
            .extra_warnings(true)
            .warnings_into_errors(true)
            .compile("wsh_git");
        println!("cargo:rustc-link-lib=z");
    }
}
