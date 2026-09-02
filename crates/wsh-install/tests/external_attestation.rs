use std::env;
use std::fs;

use wsh_install::{GithubBuildIdentity, verify_github_build_provenance};

const ARTIFACT_SHA256: &str = "83d5c2ccad5498f58bf6368acb1ab32588cf43ab3a4b1c301bf36328b1c8bd60";
const SOURCE_COMMIT: &str = "b300f2ec7ec9dc9addc39b2ad88c54097ded7ca0";

fn identity<'a>() -> GithubBuildIdentity<'a> {
    GithubBuildIdentity {
        repository: "cli/cli",
        owner_id: 59_704_711,
        repository_id: 212_613_049,
        source_ref: "refs/heads/trunk",
        source_commit: SOURCE_COMMIT,
        signer_workflow: ".github/workflows/deployment.yml",
        signer_commit: SOURCE_COMMIT,
    }
}

#[test]
#[ignore = "run through tests/external-attestation.zsh with the pinned public fixture"]
fn verifies_real_github_actions_provenance_and_rejects_substitution() {
    let path = env::var_os("WSH_EXTERNAL_ATTESTATION")
        .expect("WSH_EXTERNAL_ATTESTATION must name the pinned external fixture");
    let bytes = fs::read(path).expect("external attestation fixture must be readable");

    let name = verify_github_build_provenance(ARTIFACT_SHA256, &bytes, &identity())
        .expect("real GitHub Actions attestation must verify");
    assert_eq!(name.as_deref(), Some("gh_2.96.0_linux_amd64.tar.gz"));

    assert!(verify_github_build_provenance(&"0".repeat(64), &bytes, &identity()).is_err());

    let mut wrong = identity();
    wrong.source_ref = "refs/tags/v2.96.0";
    assert!(verify_github_build_provenance(ARTIFACT_SHA256, &bytes, &wrong).is_err());

    let mut wrong = identity();
    wrong.source_commit = "0000000000000000000000000000000000000000";
    assert!(verify_github_build_provenance(ARTIFACT_SHA256, &bytes, &wrong).is_err());

    let mut wrong = identity();
    wrong.signer_workflow = ".github/workflows/other.yml";
    assert!(verify_github_build_provenance(ARTIFACT_SHA256, &bytes, &wrong).is_err());

    let mut wrong = identity();
    wrong.repository = "other/cli";
    assert!(verify_github_build_provenance(ARTIFACT_SHA256, &bytes, &wrong).is_err());

    assert!(verify_github_build_provenance(ARTIFACT_SHA256, b"{}", &identity()).is_err());
}
