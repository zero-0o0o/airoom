use std::path::Path;

#[test]
fn test_airoom_artifacts_live_under_canonical_directory() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"));
    let artifacts_dir = root.join("airoom").join("artifacts");

    assert!(
        artifacts_dir.exists() && artifacts_dir.is_dir(),
        "airoom/artifacts directory must exist"
    );

    // Verify Graphify output is in canonical location
    let graphify_out = artifacts_dir.join("graphify-out");
    assert!(
        graphify_out.exists() && graphify_out.is_dir(),
        "Graphify output must exist under airoom/artifacts/graphify-out"
    );

    // Verify Superpowers artifacts are in canonical locations
    let sp_specs = artifacts_dir.join("docs").join("superpowers").join("specs");
    assert!(
        sp_specs.exists() && sp_specs.is_dir(),
        "Superpowers specs must exist under airoom/artifacts/docs/superpowers/specs"
    );

    let sp_plans = artifacts_dir.join("docs").join("superpowers").join("plans");
    assert!(
        sp_plans.exists() && sp_plans.is_dir(),
        "Superpowers plans must exist under airoom/artifacts/docs/superpowers/plans"
    );

    let sp_brainstorm = artifacts_dir.join(".superpowers").join("brainstorm");
    assert!(
        sp_brainstorm.exists() && sp_brainstorm.is_dir(),
        "Superpowers brainstorm state must exist under airoom/artifacts/.superpowers/brainstorm"
    );

    let sp_sdd = artifacts_dir.join(".superpowers").join("sdd");
    assert!(
        sp_sdd.exists() && sp_sdd.is_dir(),
        "Superpowers SDD workspace must exist under airoom/artifacts/.superpowers/sdd"
    );
}

#[test]
fn test_unorganized_tool_defaults_absent_from_project_root() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"));

    // Ensure root remains clean and unpolluted
    assert!(
        !root.join("graphify-out").exists(),
        "Root must NOT contain default graphify-out"
    );
    assert!(
        !root.join("docs").join("superpowers").exists(),
        "Root must NOT contain default docs/superpowers"
    );
    assert!(
        !root.join(".superpowers").exists(),
        "Root must NOT contain default .superpowers"
    );
}

#[test]
fn test_registry_records_managed_artifacts() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"));
    let reg_file = root.join("airoom").join("registry.yaml");

    assert!(reg_file.exists(), "airoom/registry.yaml must exist");
    let content = std::fs::read_to_string(&reg_file).expect("Failed to read registry.yaml");

    assert!(content.contains("version: 1"));
    assert!(content.contains("graphify-out"));
    assert!(content.contains("management: managed"));
    assert!(content.contains("superpowers"));
}
