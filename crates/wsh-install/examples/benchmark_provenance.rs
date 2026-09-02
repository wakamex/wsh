use std::env;
use std::fs;
use std::process::ExitCode;
use std::time::Instant;

use wsh_install::{GithubBuildIdentity, verify_github_build_provenance};

const ARTIFACT_SHA256: &str = "83d5c2ccad5498f58bf6368acb1ab32588cf43ab3a4b1c301bf36328b1c8bd60";
const SOURCE_COMMIT: &str = "b300f2ec7ec9dc9addc39b2ad88c54097ded7ca0";

fn run() -> Result<(), String> {
    let mut args = env::args_os().skip(1);
    let attestation = args
        .next()
        .ok_or_else(|| "usage: benchmark_provenance ATTESTATION [SAMPLES]".to_owned())?;
    let samples: usize = args
        .next()
        .map(|value| {
            value
                .into_string()
                .map_err(|_| "sample count must be UTF-8".to_owned())?
                .parse()
                .map_err(|error| format!("invalid sample count: {error}"))
        })
        .transpose()?
        .unwrap_or(100);
    if samples == 0 || args.next().is_some() {
        return Err("usage: benchmark_provenance ATTESTATION [SAMPLES]".into());
    }
    let bytes =
        fs::read(attestation).map_err(|error| format!("could not read attestation: {error}"))?;
    let identity = GithubBuildIdentity {
        repository: "cli/cli",
        owner_id: 59_704_711,
        repository_id: 212_613_049,
        source_ref: "refs/heads/trunk",
        source_commit: SOURCE_COMMIT,
        signer_workflow: ".github/workflows/deployment.yml",
        signer_commit: SOURCE_COMMIT,
    };

    verify_github_build_provenance(ARTIFACT_SHA256, &bytes, &identity)?;
    println!("sample\tnanoseconds");
    for sample in 1..=samples {
        let started = Instant::now();
        verify_github_build_provenance(ARTIFACT_SHA256, &bytes, &identity)?;
        println!("{sample}\t{}", started.elapsed().as_nanos());
    }
    Ok(())
}

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("error: {error}");
            ExitCode::FAILURE
        }
    }
}
