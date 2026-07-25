use clap::{Args, Parser, Subcommand, ValueEnum};
use regex::Regex;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    collections::{BTreeMap, BTreeSet, VecDeque},
    fs,
    path::{Path, PathBuf},
};
use unicode_normalization::UnicodeNormalization;

const DETECTOR_VERSION: &str = "1";
const CHUNKER_VERSION: &str = "h2-h3-v2";
const REQUIRED_ARTIFACTS: [&str; 5] = [
    "config.json",
    "onnx/model.onnx",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
];
const PARITY_TAG: &str = "v0.5.0";
const PARITY_COMMIT: &str = "3e5307f822b015fa82b7798bc99c3354caec8554";
const PARITY_SOURCE_PATH: &str = "crates/hallouminate-adapters/src/embedder.rs";
const PARITY_RUNNER: &str = "ubuntu-24.04-x86_64";
const PARITY_EXECUTION_PROVIDER: &str = "onnxruntime-cpu";
const MODEL_POOLING: &str = "cls";
const MODEL_NORMALIZATION: &str = "l2";
const MODEL_REVISION: &str = "b637eda6144b122ccef9318e9c8dd1483399ce87";

#[derive(Parser)]
#[command(name = "skill-overlap", about = "Graph-aware skill overlap analyzer")]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    Model {
        #[command(subcommand)]
        command: ModelCommand,
    },
    VerifyParity(ParityArgs),
    Analyze(AnalyzeArgs),
    Calibration {
        #[command(subcommand)]
        command: CalibrationCommand,
    },
    Baseline {
        #[command(subcommand)]
        command: BaselineCommand,
    },
}

#[derive(Subcommand)]
enum ModelCommand {
    Fetch(ModelArgs),
}
#[derive(Args, Clone)]
struct ModelArgs {
    #[arg(long)]
    model_lock: PathBuf,
    #[arg(long)]
    model_dir: PathBuf,
}
#[derive(Args)]
struct ParityArgs {
    #[command(flatten)]
    model: ModelArgs,
    #[arg(long)]
    fixture: PathBuf,
}
#[derive(Debug, Clone, Copy, ValueEnum)]
enum Mode {
    Calibrate,
    Report,
    Check,
}
#[derive(Args)]
struct AnalyzeArgs {
    #[arg(long)]
    mode: Mode,
    #[arg(long)]
    repo: PathBuf,
    #[arg(long)]
    manifest: PathBuf,
    #[arg(long)]
    model_lock: PathBuf,
    #[arg(long)]
    model_dir: PathBuf,
    #[arg(long)]
    calibration: Option<PathBuf>,
    #[arg(long)]
    baseline: Option<PathBuf>,
    #[arg(long)]
    json_out: PathBuf,
    #[arg(long)]
    markdown_out: PathBuf,
}
#[derive(Subcommand)]
enum CalibrationCommand {
    Prepare {
        #[arg(long)]
        report: PathBuf,
        #[arg(long)]
        out: PathBuf,
    },
    Validate {
        #[arg(long)]
        calibration: PathBuf,
        #[arg(long)]
        model_lock: PathBuf,
    },
}
#[derive(Subcommand)]
enum BaselineCommand {
    Prepare {
        #[arg(long)]
        report: PathBuf,
        #[arg(long)]
        out: PathBuf,
    },
    Validate {
        #[arg(long)]
        baseline: PathBuf,
        #[arg(long)]
        calibration: PathBuf,
        #[arg(long)]
        model_lock: PathBuf,
    },
}

#[derive(Debug, Deserialize, Serialize, Clone)]
struct ModelLock {
    format: u32,
    model: String,
    revision: String,
    fastembed: String,
    dimensions: usize,
    execution_provider: String,
    threads: u8,
    batch_size: usize,
    passage_prefix: String,
    pooling: String,
    normalization: String,
    artifacts: Vec<Artifact>,
}
#[derive(Debug, Deserialize, Serialize, Clone)]
struct Artifact {
    path: String,
    sha256: String,
}
#[derive(Debug, Clone, Serialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "kebab-case")]
enum RefKind {
    MarkdownLink,
    BacktickedPath,
}
#[derive(Debug, Clone, Serialize, PartialEq, Eq, PartialOrd, Ord)]
struct RelativeRef {
    path: String,
    kind: RefKind,
}
#[derive(Debug, Deserialize, Serialize, Clone)]
struct Detector {
    version: String,
    model_lock_digest: String,
    chunker: String,
    pooling: String,
    normalization: String,
}
#[derive(Debug, Deserialize, Serialize, Clone, PartialEq)]
struct Thresholds {
    review: f32,
    block: f32,
}
#[derive(Debug, Deserialize, Serialize, Clone, PartialEq)]
struct Sample {
    left: String,
    right: String,
    score: f32,
    label: String,
}
#[derive(Debug, Deserialize, Serialize)]
struct Calibration {
    format: u32,
    status: String,
    detector: Detector,
    thresholds: Thresholds,
    samples: Vec<Sample>,
}
#[derive(Debug, Deserialize, Serialize, Clone, PartialEq)]
struct ReviewedCalibration {
    digest: String,
    thresholds: Thresholds,
}
#[derive(Debug, Deserialize, Serialize, Clone)]
struct Disposition {
    status: String,
    reason: Option<String>,
    issue: Option<String>,
    lane: String,
    graph_class: String,
    duplicate_tokens_estimate: usize,
    #[serde(default)]
    component_tokens_estimate: usize,
}
#[derive(Debug, Deserialize, Serialize)]
struct Baseline {
    format: u32,
    status: String,
    detector: Detector,
    calibration_digest: String,
    block_threshold: f32,
    findings: BTreeMap<String, Disposition>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
struct Span {
    start: usize,
    end: usize,
}
#[derive(Debug, Clone, Serialize)]
struct Section {
    path: String,
    headings: Vec<String>,
    span: Span,
    body: String,
    refs: Vec<RelativeRef>,
    pointer: bool,
}
#[derive(Debug, Clone)]
struct Document {
    path: String,
    refs: Vec<RelativeRef>,
    sections: Vec<Section>,
}
#[derive(Debug, Clone, Serialize)]
struct Chunk {
    endpoint: Endpoint,
    payload: String,
    evidence: String,
    original_excerpt: String,
    tokens: usize,
    original_span: Span,
}
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
struct Endpoint {
    path: String,
    heading_path: Vec<String>,
    part: usize,
    source_hash: String,
    span: Span,
}
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
struct GraphClass {
    directly_linked: bool,
    directed_distance: Option<usize>,
    undirected_distance: Option<usize>,
    same_component: bool,
    same_skill: bool,
    disconnected: bool,
}
#[derive(Debug, Clone, Serialize)]
struct Finding {
    id: String,
    lane: String,
    detector: String,
    kind: String,
    left: Chunk,
    right: Chunk,
    graph: GraphClass,
    score: Option<f32>,
    duplicate_tokens_estimate: usize,
}
#[derive(Debug, Serialize, Deserialize)]
struct Report {
    format: u32,
    detector: Detector,
    mode: String,
    findings: Vec<ReportFinding>,
    #[serde(default)]
    duplicate_components: Vec<DuplicateComponent>,
    frontmatter: Vec<Advisory>,
    trends: Trends,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    calibration: Option<CalibrationData>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    reviewed_calibration: Option<ReviewedCalibration>,
}
#[derive(Debug, Serialize, Deserialize, Clone, PartialEq)]
struct ReportFinding {
    id: String,
    lane: String,
    detector: String,
    kind: String,
    left: ReportEndpoint,
    right: ReportEndpoint,
    graph: GraphClass,
    cosine: Option<f32>,
    duplicate_tokens_estimate: usize,
    disposition: String,
}
#[derive(Debug, Serialize, Deserialize, Clone, PartialEq)]
struct ReportEndpoint {
    path: String,
    heading_path: Vec<String>,
    part: usize,
    source_hash: String,
    span: Span,
    original_excerpt: String,
    token_count: usize,
}

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq, Eq)]
struct DuplicateComponent {
    id: String,
    endpoints: Vec<String>,
    finding_ids: Vec<String>,
    redundant_tokens_estimate: usize,
}
#[derive(Debug, Serialize, Deserialize, PartialEq)]
struct CalibrationData {
    score_distribution: Vec<ScoreStratum>,
    samples: Vec<Sample>,
}
#[derive(Debug, Serialize, Deserialize, PartialEq)]
struct ScoreStratum {
    min_score: f32,
    max_score: f32,
    count: usize,
}
#[derive(Debug)]
struct FrontmatterValue {
    path: String,
    field: String,
    value: String,
}
#[derive(Debug, Serialize, Deserialize)]
struct Advisory {
    left: String,
    right: String,
    field: String,
    left_value: String,
    right_value: String,
    score: f32,
}
#[derive(Debug, Default)]
struct TrendAccumulator {
    current_findings: usize,
    baseline_findings: usize,
    current_estimated_duplicate_tokens: usize,
    baseline_estimated_duplicate_tokens: usize,
}
#[derive(Debug, Serialize, Deserialize, Clone, PartialEq, Eq, PartialOrd, Ord)]
struct TrendGroup {
    lane: String,
    graph_class: String,
    disposition: String,
    current_findings: usize,
    baseline_findings: usize,
    current_estimated_duplicate_tokens: usize,
    baseline_estimated_duplicate_tokens: usize,
}
#[derive(Debug, Serialize, Deserialize)]
struct Trends {
    groups: Vec<TrendGroup>,
}

fn main() -> Result<(), String> {
    match Cli::parse().command {
        Command::Model {
            command: ModelCommand::Fetch(args),
        } => model_fetch(&args),
        Command::VerifyParity(args) => verify_parity(args),
        Command::Analyze(args) => analyze(args),
        Command::Calibration { command } => calibration(command),
        Command::Baseline { command } => baseline(command),
    }
}

fn read_json<T: for<'a> Deserialize<'a>>(path: &Path) -> Result<T, String> {
    serde_json::from_str(&fs::read_to_string(path).map_err(ioerr)?)
        .map_err(|e| format!("{}: {e}", path.display()))
}
fn read_yaml<T: for<'a> Deserialize<'a>>(path: &Path) -> Result<T, String> {
    serde_yaml::from_str(&fs::read_to_string(path).map_err(ioerr)?)
        .map_err(|e| format!("{}: {e}", path.display()))
}
fn write_yaml<T: Serialize>(path: &Path, value: &T) -> Result<(), String> {
    fs::write(
        path,
        serde_yaml::to_string(value).map_err(|e| e.to_string())?,
    )
    .map_err(ioerr)
}
fn ioerr(e: std::io::Error) -> String {
    e.to_string()
}
fn digest(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}
fn model_digest(lock: &ModelLock) -> Result<String, String> {
    Ok(digest(
        &serde_json::to_vec(lock).map_err(|e| e.to_string())?,
    ))
}

fn validated_model_digest(path: &Path) -> Result<String, String> {
    let lock: ModelLock = read_json(path)?;
    validate_model_lock(&lock)?;
    model_digest(&lock)
}

fn validate_model_lock(lock: &ModelLock) -> Result<(), String> {
    if lock.format != 1
        || lock.model != "snowflake/snowflake-arctic-embed-s"
        || lock.revision != MODEL_REVISION
        || lock.fastembed != "5.17.3"
        || lock.dimensions != 384
        || lock.batch_size != 32
        || !lock.passage_prefix.is_empty()
        || lock.execution_provider != PARITY_EXECUTION_PROVIDER
        || lock.threads != 1
        || lock.pooling != MODEL_POOLING
        || lock.normalization != MODEL_NORMALIZATION
    {
        return Err(
            "model lock has incompatible embedder metadata; recalibrate and rebaseline".into(),
        );
    }
    let sha = Regex::new(r"^[a-f0-9]{64}$").unwrap();
    let mut actual = BTreeSet::new();
    for artifact in &lock.artifacts {
        let path = Path::new(&artifact.path);
        if artifact.path.is_empty()
            || path
                .components()
                .any(|component| !matches!(component, std::path::Component::Normal(_)))
        {
            return Err(format!("unsafe model artifact path {}", artifact.path));
        }
        if !actual.insert(artifact.path.as_str()) {
            return Err(format!("duplicate model artifact {}", artifact.path));
        }
        if !sha.is_match(&artifact.sha256) {
            return Err(format!("invalid SHA-256 for {}", artifact.path));
        }
    }
    let required = REQUIRED_ARTIFACTS.into_iter().collect::<BTreeSet<_>>();
    if actual != required {
        let missing = required.difference(&actual).copied().collect::<Vec<_>>();
        let unexpected = actual.difference(&required).copied().collect::<Vec<_>>();
        return Err(format!(
            "model artifact set mismatch; missing [{}], unexpected [{}]",
            missing.join(", "),
            unexpected.join(", ")
        ));
    }
    Ok(())
}

fn verify_model(lock_path: &Path, model_dir: &Path) -> Result<ModelLock, String> {
    let lock: ModelLock = read_json(lock_path)?;
    validate_model_lock(&lock)?;
    for artifact in &lock.artifacts {
        let bytes = fs::read(model_dir.join(&artifact.path))
            .map_err(|_| format!("missing locked model artifact {}", artifact.path))?;
        if digest(&bytes) != artifact.sha256 {
            return Err(format!("checksum mismatch for {}", artifact.path));
        }
    }
    Ok(lock)
}

fn model_fetch(args: &ModelArgs) -> Result<(), String> {
    let lock: ModelLock = read_json(&args.model_lock)?;
    validate_model_lock(&lock)?;
    #[cfg(feature = "model")]
    {
        fetch_locked_artifacts(&lock, &args.model_dir)?;
        verify_model(&args.model_lock, &args.model_dir)?;
        Ok(())
    }
    #[cfg(not(feature = "model"))]
    {
        let _ = lock;
        Err("rebuild with --features model to fetch the pinned model".into())
    }
}

#[cfg(feature = "model")]
fn fetch_locked_artifacts(lock: &ModelLock, model_dir: &Path) -> Result<(), String> {
    let client = reqwest::blocking::Client::builder()
        .redirect(reqwest::redirect::Policy::limited(5))
        .build()
        .map_err(|error| format!("build model downloader: {error}"))?;
    for artifact in &lock.artifacts {
        let path = model_dir.join(&artifact.path);
        if fs::read(&path)
            .ok()
            .is_some_and(|bytes| digest(&bytes) == artifact.sha256)
        {
            continue;
        }
        let url = format!(
            "https://huggingface.co/{}/resolve/{}/{}",
            lock.model, lock.revision, artifact.path
        );
        let response = client
            .get(url)
            .send()
            .map_err(|error| format!("download {}: {error}", artifact.path))?
            .error_for_status()
            .map_err(|error| format!("download {}: {error}", artifact.path))?;
        let bytes = response
            .bytes()
            .map_err(|error| format!("read {}: {error}", artifact.path))?;
        if digest(&bytes) != artifact.sha256 {
            return Err(format!("download checksum mismatch for {}", artifact.path));
        }
        let parent = path.parent().ok_or("model artifact has no parent")?;
        fs::create_dir_all(parent).map_err(ioerr)?;
        let temporary = path.with_extension("partial");
        fs::write(&temporary, bytes).map_err(ioerr)?;
        fs::rename(temporary, path).map_err(ioerr)?;
    }
    Ok(())
}

#[cfg(feature = "model")]
fn load_embedder(model_dir: &Path) -> Result<fastembed::TextEmbedding, String> {
    use fastembed::{
        InitOptionsUserDefined, Pooling, TextEmbedding, TokenizerFiles, UserDefinedEmbeddingModel,
    };
    let tokenizer = TokenizerFiles {
        tokenizer_file: fs::read(model_dir.join("tokenizer.json")).map_err(ioerr)?,
        config_file: fs::read(model_dir.join("config.json")).map_err(ioerr)?,
        special_tokens_map_file: fs::read(model_dir.join("special_tokens_map.json"))
            .map_err(ioerr)?,
        tokenizer_config_file: fs::read(model_dir.join("tokenizer_config.json")).map_err(ioerr)?,
    };
    let model = UserDefinedEmbeddingModel::new(
        fs::read(model_dir.join("onnx/model.onnx")).map_err(ioerr)?,
        tokenizer,
    )
    .with_pooling(Pooling::Cls);
    TextEmbedding::try_new_from_user_defined(
        model,
        InitOptionsUserDefined::new().with_intra_threads(1),
    )
    .map_err(|error| format!("initialize verified local ONNX model: {error}"))
}

#[cfg(feature = "model")]
fn embed_payloads(model_dir: &Path, payloads: &[String]) -> Result<Vec<Vec<f32>>, String> {
    let mut embedder = load_embedder(model_dir)?;
    let vectors = embedder
        .embed(payloads, Some(32))
        .map_err(|error| format!("embed verified local chunks: {error}"))?;
    vectors
        .into_iter()
        .map(|mut vector| {
            if vector.len() != 384 {
                return Err(format!(
                    "embedder returned {} dimensions, expected 384",
                    vector.len()
                ));
            }
            l2_normalize(&mut vector);
            Ok(vector)
        })
        .collect()
}

#[cfg(not(feature = "model"))]
fn embed_payloads(_: &Path, _: &[String]) -> Result<Vec<Vec<f32>>, String> {
    Err("rebuild with --features model for semantic analysis".into())
}

#[cfg(feature = "model")]
fn l2_normalize(vector: &mut [f32]) {
    let norm = vector.iter().map(|value| value * value).sum::<f32>().sqrt();
    if norm > f32::EPSILON {
        for value in vector {
            *value /= norm;
        }
    }
}

fn cosine(left: &[f32], right: &[f32]) -> f32 {
    left.iter().zip(right).map(|(a, b)| a * b).sum()
}

fn validate_fixture_provenance(value: &serde_json::Value, lock_digest: &str) -> Result<(), String> {
    let h = value
        .get("hallouminate")
        .and_then(|value| value.as_object())
        .ok_or("fixture lacks hallouminate provenance")?;
    for (key, expected) in [
        ("tag", PARITY_TAG),
        ("commit", PARITY_COMMIT),
        ("source_path", PARITY_SOURCE_PATH),
        ("runner", PARITY_RUNNER),
        ("execution_provider", PARITY_EXECUTION_PROVIDER),
        ("pooling", MODEL_POOLING),
        ("normalization", MODEL_NORMALIZATION),
    ] {
        let actual = h.get(key).and_then(|value| value.as_str()).unwrap_or("");
        if actual != expected {
            return Err(format!(
                "fixture {key} must be {expected:?}, found {actual:?}; regenerate on the locked Ubuntu x86_64 runner"
            ));
        }
    }
    if h.get("threads").and_then(|value| value.as_u64()) != Some(1) {
        return Err("fixture threads must be 1".into());
    }
    if value.get("model_lock_digest").and_then(|v| v.as_str()) != Some(lock_digest) {
        return Err("fixture model-lock digest mismatch".into());
    }
    let cases = value
        .get("cases")
        .and_then(|value| value.as_array())
        .ok_or("fixture lacks cases")?;
    if cases.is_empty() {
        return Err("fixture has no golden vectors".into());
    }
    for case in cases {
        let valid_input = case
            .get("input")
            .and_then(|value| value.as_str())
            .is_some_and(|input| !input.is_empty());
        let valid_output = case
            .get("output")
            .and_then(|value| value.as_array())
            .is_some_and(|output| {
                output.len() == 384 && output.iter().all(|value| value.as_f64().is_some())
            });
        if !valid_input || !valid_output {
            return Err("fixture case lacks input or numeric 384-value output".into());
        }
    }
    Ok(())
}

fn verify_parity(args: ParityArgs) -> Result<(), String> {
    let lock = verify_model(&args.model.model_lock, &args.model.model_dir)?;
    let value: serde_json::Value = read_json(&args.fixture)?;
    validate_fixture_provenance(&value, &model_digest(&lock)?)?;
    let cases = value["cases"].as_array().unwrap();
    #[cfg(feature = "model")]
    {
        let inputs = cases
            .iter()
            .map(|case| case["input"].as_str().unwrap().to_owned())
            .collect::<Vec<_>>();
        let actual = embed_payloads(&args.model.model_dir, &inputs)?;
        for (case, actual) in cases.iter().zip(actual) {
            let expected = case["output"].as_array().unwrap();
            let max_error = expected
                .iter()
                .zip(&actual)
                .map(|(expected, actual)| (expected.as_f64().unwrap() as f32 - actual).abs())
                .fold(0.0f32, f32::max);
            let expected = expected
                .iter()
                .map(|value| value.as_f64().unwrap() as f32)
                .collect::<Vec<_>>();
            if max_error > 1e-6 || cosine(&expected, &actual) < 0.999999 {
                return Err(format!(
                    "parity failed: max error {max_error}, cosine {}",
                    cosine(&expected, &actual)
                ));
            }
        }
        Ok(())
    }
    #[cfg(not(feature = "model"))]
    {
        let _ = cases;
        Err("rebuild with --features model for ONNX parity verification".into())
    }
}

fn load_roots(repo: &Path, manifest: &Path) -> Result<Vec<PathBuf>, String> {
    let canonical_repo = fs::canonicalize(repo).map_err(ioerr)?;
    let value: serde_json::Value = read_json(manifest)?;
    value
        .get("skills")
        .and_then(|v| v.as_array())
        .ok_or_else(|| "manifest lacks skills array".to_owned())?
        .iter()
        .map(|value| {
            let raw = value
                .as_str()
                .ok_or_else(|| "manifest skill is not a path".to_owned())?;
            let relative = Path::new(raw);
            if relative.is_absolute() {
                return Err(format!("manifest skill path must be relative: {raw}"));
            }
            if relative
                .components()
                .any(|component| matches!(component, std::path::Component::ParentDir))
            {
                return Err(format!(
                    "manifest skill path contains parent traversal: {raw}"
                ));
            }
            let root = repo.join(relative);
            let canonical_root = fs::canonicalize(&root).map_err(ioerr)?;
            if !canonical_root.starts_with(&canonical_repo) {
                return Err(format!("manifest skill root escapes repository: {raw}"));
            }
            Ok(root)
        })
        .collect()
}

fn markdown_files(repo: &Path, root: &Path, out: &mut Vec<PathBuf>) -> Result<(), String> {
    fn visit(repo: &Path, root: &Path, out: &mut Vec<PathBuf>) -> Result<(), String> {
        let metadata = fs::symlink_metadata(root).map_err(ioerr)?;
        if metadata.file_type().is_symlink() {
            return Err(format!("refusing symlink traversal at {}", root.display()));
        }
        let canonical_root = fs::canonicalize(root).map_err(ioerr)?;
        if !canonical_root.starts_with(repo) {
            return Err(format!(
                "Markdown root escapes repository: {}",
                root.display()
            ));
        }
        for item in fs::read_dir(root).map_err(ioerr)? {
            let path = item.map_err(ioerr)?.path();
            let metadata = fs::symlink_metadata(&path).map_err(ioerr)?;
            if metadata.file_type().is_symlink() {
                return Err(format!("refusing symlink traversal at {}", path.display()));
            }
            if metadata.is_dir() {
                visit(repo, &path, out)?;
            } else if path.extension().is_some_and(|extension| extension == "md") {
                out.push(path);
            }
        }
        Ok(())
    }

    let canonical_repo = fs::canonicalize(repo).map_err(ioerr)?;
    visit(&canonical_repo, root, out)
}

fn parse_document(path: &Path, repo: &Path, counter: &TokenCounter) -> Result<Document, String> {
    let text = fs::read_to_string(path).map_err(ioerr)?;
    let rel = path
        .strip_prefix(repo)
        .unwrap_or(path)
        .to_string_lossy()
        .replace('\\', "/");
    let mut h1 = String::new();
    let mut h2 = String::new();
    let mut current: Option<(Vec<String>, usize, Vec<String>)> = None;
    let mut sections = Vec::new();
    let fence_marker = |line: &str| {
        let indentation = line.bytes().take_while(|byte| *byte == b' ').count();
        if indentation > 3 {
            return None;
        }
        let trimmed = &line[indentation..];
        let marker = trimmed.chars().next()?;
        if !matches!(marker, '`' | '~') {
            return None;
        }
        let length = trimmed
            .chars()
            .take_while(|character| *character == marker)
            .count();
        (length >= 3).then(|| {
            let blank_suffix = trimmed[length..]
                .bytes()
                .all(|byte| matches!(byte, b' ' | b'\t'));
            (marker, length, blank_suffix)
        })
    };
    let mut fence = None::<(char, usize)>;
    let finish = |current: &mut Option<(Vec<String>, usize, Vec<String>)>,
                  end: usize,
                  sections: &mut Vec<Section>|
     -> Result<(), String> {
        if let Some((headings, start, lines)) = current.take() {
            let body = lines.join("\n");
            let refs = extract_typed_relative_refs(&body);
            let pointer = pointer_only(&body, &refs, counter)?;
            sections.push(Section {
                path: rel.clone(),
                headings,
                span: Span { start, end },
                body,
                refs,
                pointer,
            });
        }
        Ok(())
    };
    for (index, line) in text.lines().enumerate() {
        let line_number = index + 1;
        if let Some((marker, length, blank_suffix)) = fence_marker(line) {
            match fence {
                None => fence = Some((marker, length)),
                Some((opening_marker, opening_length))
                    if marker == opening_marker
                        && length >= opening_length
                        && blank_suffix =>
                {
                    fence = None;
                }
                Some(_) => {}
            }
            if let Some((_, _, body)) = &mut current {
                body.push(line.to_owned());
            }
            continue;
        }
        if fence.is_none() {
            if let Some(title) = line.strip_prefix("# ") {
                h1 = title.trim().to_owned();
                h2.clear();
                continue;
            }
            let heading = line.trim_start();
            let level = heading
                .chars()
                .take_while(|character| *character == '#')
                .count();
            if level == 2 && heading.as_bytes().get(level) == Some(&b' ') {
                finish(&mut current, line_number.saturating_sub(1), &mut sections)?;
                h2 = heading[level + 1..].trim().to_owned();
                current = Some((vec![h1.clone(), h2.clone()], line_number + 1, Vec::new()));
                continue;
            }
            if level == 3 && heading.as_bytes().get(level) == Some(&b' ') {
                finish(&mut current, line_number.saturating_sub(1), &mut sections)?;
                let mut headings = vec![h1.clone()];
                if !h2.is_empty() {
                    headings.push(h2.clone());
                }
                headings.push(heading[level + 1..].trim().to_owned());
                current = Some((headings, line_number + 1, Vec::new()));
                continue;
            }
        }
        if let Some((_, _, body)) = &mut current {
            body.push(line.to_owned());
        }
    }
    finish(&mut current, text.lines().count(), &mut sections)?;
    Ok(Document {
        path: rel,
        refs: extract_typed_relative_refs(&text),
        sections,
    })
}

fn extract_typed_relative_refs(text: &str) -> Vec<RelativeRef> {
    let links = Regex::new(r"\[[^\]]*\]\(([^)\s]+)\)").unwrap();
    let ticks = Regex::new(r"`([^`]+)`").unwrap();
    let prose =
        Regex::new(r"^(?:\.\./)+[\w./-]+\.md(?:#[\w-]+)?$|^references/[\w./-]+\.md(?:#[\w-]+)?$")
            .unwrap();
    let mut refs = Vec::new();
    for capture in links.captures_iter(text) {
        let raw = &capture[1];
        if !["http://", "https://", "mailto:", "#"]
            .iter()
            .any(|prefix| raw.starts_with(prefix))
        {
            let path = raw.split('#').next().unwrap();
            if path.ends_with(".md") {
                refs.push(RelativeRef {
                    path: path.to_owned(),
                    kind: RefKind::MarkdownLink,
                });
            }
        }
    }
    for capture in ticks.captures_iter(text) {
        let candidate = capture[1].split(" § ").next().unwrap();
        if prose.is_match(candidate) {
            refs.push(RelativeRef {
                path: candidate.split('#').next().unwrap().to_owned(),
                kind: RefKind::BacktickedPath,
            });
        }
    }
    refs
}

#[cfg(test)]
fn extract_relative_refs(text: &str) -> Vec<String> {
    extract_typed_relative_refs(text)
        .into_iter()
        .map(|reference| reference.path)
        .collect()
}

fn pointer_only(body: &str, refs: &[RelativeRef], counter: &TokenCounter) -> Result<bool, String> {
    let cleaned = Regex::new(r"(?s)<!--.*?-->").unwrap().replace_all(body, "");
    let trimmed = cleaned
        .lines()
        .filter(|line| !matches!(line.trim(), "---" | "***" | "___"))
        .collect::<Vec<_>>()
        .join("\n");
    let normalized = normalize(&trimmed);
    let has_list = Regex::new(r"(?m)^\s*(?:[-*+]|[0-9]+\.)\s+")
        .unwrap()
        .is_match(&trimmed);
    let has_table = trimmed
        .lines()
        .any(|line| line.trim().starts_with('|') || line.matches('|').count() >= 2);
    if refs.len() != 1
        || counter.count(&normalized)? > 40
        || normalized.contains("```")
        || normalized.contains("~~~")
        || has_list
        || has_table
    {
        return Ok(false);
    }
    let target = regex::escape(&refs[0].path);
    let syntactic_ref =
        format!(r"(?:\[[^\]\n]*\]\({target}(?:#[^\s)]+)?\)|`{target}(?:#[\w-]+)?(?: § [^`]+)?`)",);
    let pattern = format!(
        r"^(?:See {syntactic_ref}|Full .+ in {syntactic_ref}|.+ lives in {syntactic_ref})[.!?]?$"
    );
    Ok(Regex::new(&pattern).unwrap().is_match(&normalized))
}

fn normalize(text: &str) -> String {
    text.replace("\r\n", "\n")
        .nfc()
        .collect::<String>()
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
}
enum TokenCounter {
    #[cfg(test)]
    Test,
    #[cfg(test)]
    TestChars,
    #[cfg(feature = "model")]
    Model(Box<tokenizers::Tokenizer>),
    #[cfg(all(not(test), not(feature = "model")))]
    Unavailable,
}

impl TokenCounter {
    fn count(&self, text: &str) -> Result<usize, String> {
        match self {
            #[cfg(test)]
            Self::Test => Ok(text.split_whitespace().count()),
            #[cfg(test)]
            Self::TestChars => Ok(text.chars().count()),
            #[cfg(feature = "model")]
            Self::Model(tokenizer) => tokenizer
                .encode(text, true)
                .map(|encoding| encoding.len())
                .map_err(|error| format!("count model tokens: {error}")),
            #[cfg(all(not(test), not(feature = "model")))]
            Self::Unavailable => Err("pinned model tokenizer is unavailable".into()),
        }
    }
}

#[cfg(feature = "model")]
fn model_token_counter(model_dir: &Path) -> Result<TokenCounter, String> {
    tokenizers::Tokenizer::from_file(model_dir.join("tokenizer.json"))
        .map(Box::new)
        .map(TokenCounter::Model)
        .map_err(|error| format!("load verified model tokenizer: {error}"))
}

#[cfg(not(feature = "model"))]
fn model_token_counter(_: &Path) -> Result<TokenCounter, String> {
    Err("rebuild with --features model for model-token chunking".into())
}

#[derive(Clone)]
struct TableContext {
    header: String,
    header_line: usize,
}

#[derive(Clone)]
struct SplitLine {
    text: String,
    source_line: usize,
    boundary_after: u8,
    list_group: Option<usize>,
    table: Option<TableContext>,
}

struct SplitPiece {
    body: String,
    synthetic_context: Option<String>,
    span: Span,
}

fn list_indent(line: &str) -> Option<usize> {
    let indent = line.len() - line.trim_start().len();
    let trimmed = line.trim_start();
    let unordered = ["- ", "* ", "+ "]
        .iter()
        .any(|prefix| trimmed.starts_with(prefix));
    let ordered = trimmed.split_once(". ").is_some_and(|(prefix, _)| {
        !prefix.is_empty() && prefix.bytes().all(|byte| byte.is_ascii_digit())
    });
    (unordered || ordered).then_some(indent)
}

fn list_groups(lines: &[&str]) -> Vec<Option<usize>> {
    let mut groups = vec![None; lines.len()];
    let mut active = None::<(usize, usize)>;
    let mut next_group = 0;
    for (index, line) in lines.iter().enumerate() {
        if let Some(indent) = list_indent(line) {
            if active.is_none_or(|(root_indent, _)| indent <= root_indent) {
                next_group += 1;
                active = Some((indent, next_group));
            }
            groups[index] = active.map(|(_, group)| group);
        } else if let Some((root_indent, group)) = active {
            let indent = line.len() - line.trim_start().len();
            if line.trim().is_empty() || indent > root_indent {
                groups[index] = Some(group);
            } else {
                active = None;
            }
        }
    }
    groups
}

fn is_table_row(line: &str) -> bool {
    let trimmed = line.trim();
    !trimmed.is_empty() && trimmed.contains('|')
}

fn table_contexts(lines: &[&str], section_start: usize) -> Vec<Option<TableContext>> {
    let delimiter = Regex::new(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$").unwrap();
    let mut contexts = vec![None; lines.len()];
    let mut index = 0;
    while index + 1 < lines.len() {
        if is_table_row(lines[index]) && delimiter.is_match(lines[index + 1]) {
            let context = TableContext {
                header: lines[index].to_owned(),
                header_line: section_start + index,
            };
            let mut end = index;
            while end < lines.len() && is_table_row(lines[end]) {
                contexts[end] = Some(context.clone());
                end += 1;
            }
            index = end;
        } else {
            index += 1;
        }
    }
    contexts
}

fn sentence_fragments(line: &str) -> Vec<String> {
    let mut fragments = Vec::new();
    let mut start = 0;
    for (index, character) in line.char_indices() {
        if matches!(character, '.' | '!' | '?') {
            let end = index + character.len_utf8();
            if line[end..].chars().next().is_some_and(char::is_whitespace) {
                let fragment = line[start..end].trim().to_owned();
                if !fragment.is_empty() {
                    fragments.push(fragment);
                }
                start = end;
            }
        }
    }
    let tail = line[start..].trim().to_owned();
    if !tail.is_empty() || fragments.is_empty() {
        fragments.push(tail);
    }
    fragments
}

fn fixed_token_windows(
    line: &str,
    hard_limit: usize,
    counter: &TokenCounter,
) -> Result<Vec<String>, String> {
    fn split_unit(
        unit: &str,
        hard_limit: usize,
        counter: &TokenCounter,
    ) -> Result<Vec<String>, String> {
        let mut pieces = Vec::new();
        let mut start = 0;
        while start < unit.len() {
            let remaining = &unit[start..];
            if counter.count(remaining)? <= hard_limit {
                pieces.push(remaining.to_owned());
                break;
            }
            let boundaries = remaining
                .char_indices()
                .skip(1)
                .map(|(index, _)| index)
                .chain(std::iter::once(remaining.len()))
                .collect::<Vec<_>>();
            let mut low = 0;
            let mut high = boundaries.len();
            while low < high {
                let middle = (low + high).div_ceil(2);
                if counter.count(&remaining[..boundaries[middle - 1]])? <= hard_limit {
                    low = middle;
                } else {
                    high = middle - 1;
                }
            }
            if low == 0 {
                return Err("a source character exceeds the 480-token chunk cap".into());
            }
            let end = boundaries[low - 1];
            pieces.push(remaining[..end].to_owned());
            start += end;
        }
        Ok(pieces)
    }

    let mut windows = Vec::new();
    let mut window = Vec::new();
    for word in line.split_whitespace() {
        let mut candidate = window.clone();
        candidate.push(word);
        if counter.count(&candidate.join(" "))? <= hard_limit {
            window = candidate;
        } else {
            if !window.is_empty() {
                windows.push(window.join(" "));
                window.clear();
            }
            if counter.count(word)? <= hard_limit {
                window.push(word);
            } else {
                windows.extend(split_unit(word, hard_limit, counter)?);
            }
        }
    }
    if !window.is_empty() {
        windows.push(window.join(" "));
    }
    Ok(windows)
}

fn join_split_lines(lines: &[SplitLine]) -> String {
    let mut body = String::new();
    for (index, line) in lines.iter().enumerate() {
        if index > 0 {
            if lines[index - 1].source_line == line.source_line {
                body.push(' ');
            } else {
                body.push('\n');
            }
        }
        body.push_str(&line.text);
    }
    body
}

fn boundary_rank(lines: &[SplitLine], cut: usize) -> u8 {
    if cut < lines.len() && lines[cut].text.trim_start().starts_with("#### ") {
        8
    } else if lines[cut - 1].list_group.is_some()
        && lines.get(cut).and_then(|line| line.list_group) != lines[cut - 1].list_group
    {
        6
    } else {
        lines[cut - 1].boundary_after
    }
}

fn valid_cut(lines: &[SplitLine], cut: usize) -> bool {
    if cut == lines.len() {
        return true;
    }
    let left = &lines[cut - 1];
    let right = &lines[cut];
    if left.list_group.is_some() && left.list_group == right.list_group {
        return false;
    }
    !left.table.as_ref().is_some_and(|table| {
        left.source_line == table.header_line && right.source_line == table.header_line + 1
    })
}

fn split_section(
    section: &Section,
    payload_budget: usize,
    counter: &TokenCounter,
) -> Result<Vec<SplitPiece>, String> {
    let hard_limit = 480usize.saturating_sub(payload_budget).max(1);
    if counter.count(&section.body)? <= hard_limit {
        return Ok(vec![SplitPiece {
            body: section.body.clone(),
            synthetic_context: None,
            span: section.span.clone(),
        }]);
    }
    let source_lines = section.body.lines().collect::<Vec<_>>();
    let groups = list_groups(&source_lines);
    let tables = table_contexts(&source_lines, section.span.start);
    let mut lines = Vec::new();
    for (offset, line) in source_lines.iter().enumerate() {
        let source_line = section.span.start + offset;
        let structural = groups[offset].is_some() || tables[offset].is_some();
        let sentences = if structural {
            vec![(*line).to_owned()]
        } else {
            sentence_fragments(line)
        };
        for sentence in sentences {
            let fragments = if counter.count(&sentence)? <= hard_limit {
                vec![sentence]
            } else {
                fixed_token_windows(&sentence, hard_limit, counter)?
            };
            let fragment_count = fragments.len();
            for (fragment_index, text) in fragments.into_iter().enumerate() {
                let last_fragment = fragment_index + 1 == fragment_count;
                let trimmed = text.trim_start();
                let boundary_after = if !last_fragment {
                    1
                } else if trimmed.is_empty() {
                    7
                } else if tables[offset].is_some() {
                    5
                } else if trimmed.starts_with('>')
                    && source_lines
                        .get(offset + 1)
                        .is_none_or(|next| !next.trim_start().starts_with('>'))
                {
                    4
                } else if text.trim_end().ends_with(['.', '!', '?']) {
                    3
                } else {
                    2
                };
                lines.push(SplitLine {
                    text,
                    source_line,
                    boundary_after,
                    list_group: groups[offset],
                    table: tables[offset].clone(),
                });
            }
        }
    }

    let mut pieces = Vec::new();
    let mut start = 0;
    while start < lines.len() {
        let synthetic_context = lines[start].table.as_ref().and_then(|table| {
            (table.header_line < lines[start].source_line).then(|| table.header.clone())
        });
        let synthetic_tokens = synthetic_context
            .as_deref()
            .map(|header| counter.count(header))
            .transpose()?
            .unwrap_or(0);
        let cap = hard_limit.saturating_sub(synthetic_tokens).max(1);
        let target = 384usize
            .saturating_sub(payload_budget + synthetic_tokens)
            .max(1);
        let mut target_candidates = Vec::new();
        let mut cap_candidates = Vec::new();
        let mut fallback_target_candidates = Vec::new();
        let mut fallback_cap_candidates = Vec::new();
        for end in start + 1..=lines.len() {
            let body = join_split_lines(&lines[start..end]);
            let tokens = counter.count(&body)?;
            if tokens > cap {
                break;
            }
            if valid_cut(&lines, end) {
                cap_candidates.push(end);
                if tokens <= target {
                    target_candidates.push(end);
                }
            } else if lines[start].list_group.is_some_and(|group| {
                lines[end - 1].list_group == Some(group)
                    && lines.get(end).and_then(|line| line.list_group) == Some(group)
            }) {
                fallback_cap_candidates.push(end);
                if tokens <= target {
                    fallback_target_candidates.push(end);
                }
            }
        }
        let candidates = if !target_candidates.is_empty() {
            &target_candidates
        } else if !cap_candidates.is_empty() {
            &cap_candidates
        } else if !fallback_target_candidates.is_empty() {
            &fallback_target_candidates
        } else {
            &fallback_cap_candidates
        };
        let cut = candidates
            .iter()
            .copied()
            .max_by_key(|cut| (boundary_rank(&lines, *cut), *cut))
            .ok_or("a complete structural unit exceeds the 480-token chunk cap")?;
        pieces.push(SplitPiece {
            body: join_split_lines(&lines[start..cut]),
            synthetic_context,
            span: Span {
                start: lines[start].source_line,
                end: lines[cut - 1].source_line,
            },
        });
        start = cut;
    }
    Ok(pieces)
}

fn chunks(documents: &[Document], counter: &TokenCounter) -> Result<Vec<Chunk>, String> {
    let mut chunks = Vec::new();
    for section in documents
        .iter()
        .flat_map(|document| document.sections.iter())
        .filter(|section| !section.pointer && !normalize(&section.body).is_empty())
    {
        let heading_path = section.headings.join(" > ");
        let payload_budget = counter.count(&format!("{heading_path} > part 999999/999999"))?;
        let pieces = split_section(section, payload_budget, counter)?;
        let parts = pieces.len();
        for (index, piece) in pieces.into_iter().enumerate() {
            let part = index + 1;
            let heading = if parts == 1 {
                heading_path.clone()
            } else {
                format!("{heading_path} > part {part}/{parts}")
            };
            let payload = match &piece.synthetic_context {
                Some(context) => format!("{heading}\n{context}\n{}", piece.body),
                None => format!("{heading}\n{}", piece.body),
            };
            if counter.count(&payload)? > 480 {
                return Err("chunk payload exceeds the 480-token cap".into());
            }
            chunks.push(Chunk {
                evidence: normalize(&piece.body),
                original_excerpt: piece.body.clone(),
                endpoint: Endpoint {
                    path: section.path.clone(),
                    heading_path: section.headings.clone(),
                    part,
                    source_hash: digest(normalize(&section.body).as_bytes()),
                    span: piece.span,
                },
                payload,
                tokens: counter.count(&piece.body)?,
                original_span: section.span.clone(),
            });
        }
    }
    Ok(chunks)
}
fn section_chunk(section: &Section, counter: &TokenCounter) -> Result<Chunk, String> {
    let evidence = normalize(&section.body);
    Ok(Chunk {
        endpoint: Endpoint {
            path: section.path.clone(),
            heading_path: section.headings.clone(),
            part: 1,
            source_hash: digest(evidence.as_bytes()),
            span: section.span.clone(),
        },
        payload: section.body.clone(),
        evidence,
        original_excerpt: section.body.clone(),
        tokens: counter.count(&section.body)?,
        original_span: section.span.clone(),
    })
}

fn same_original_section(left: &Chunk, right: &Chunk) -> bool {
    left.endpoint.path == right.endpoint.path
        && left.endpoint.heading_path == right.endpoint.heading_path
        && left.endpoint.source_hash == right.endpoint.source_hash
        && left.original_span == right.original_span
}
fn semantic_pair_eligible(left: &Chunk, right: &Chunk) -> bool {
    !same_original_section(left, right) && left.endpoint.source_hash != right.endpoint.source_hash
}

fn exact_findings(
    documents: &[Document],
    counter: &TokenCounter,
    edges: &GraphEdges,
    owner: &BTreeMap<String, usize>,
) -> Result<Vec<Finding>, String> {
    let sections = documents
        .iter()
        .flat_map(|document| &document.sections)
        .filter(|section| !normalize(&section.body).is_empty())
        .collect::<Vec<_>>();
    let mut findings = Vec::new();
    for (index, left_section) in sections.iter().enumerate() {
        let left_normalized = normalize(&left_section.body);
        for right_section in sections.iter().skip(index + 1) {
            if left_normalized != normalize(&right_section.body) {
                continue;
            }
            let left = section_chunk(left_section, counter)?;
            let right = section_chunk(right_section, counter)?;
            findings.push(Finding {
                id: identity("exact", &left, &right, None),
                lane: "body".into(),
                detector: DETECTOR_VERSION.into(),
                kind: "exact".into(),
                graph: graph_class(edges, owner, &left, &right),
                duplicate_tokens_estimate: left.tokens.min(right.tokens),
                left,
                right,
                score: None,
            });
        }
    }
    Ok(findings)
}

fn lexical_path(path: &Path) -> String {
    let mut parts = Vec::new();
    for component in path.components() {
        match component {
            std::path::Component::CurDir => {}
            std::path::Component::ParentDir => {
                if parts.last().is_some_and(|part| part != "..") {
                    parts.pop();
                } else {
                    parts.push("..".to_owned());
                }
            }
            std::path::Component::Normal(part) => {
                parts.push(part.to_string_lossy().into_owned());
            }
            std::path::Component::RootDir | std::path::Component::Prefix(_) => {}
        }
    }
    parts.join("/")
}

type GraphEdges = BTreeMap<String, BTreeSet<(String, RefKind)>>;

fn graph(
    documents: &[Document],
    roots: &[PathBuf],
    repo: &Path,
) -> (GraphEdges, BTreeMap<String, usize>) {
    let paths = documents
        .iter()
        .map(|document| document.path.clone())
        .collect::<BTreeSet<_>>();
    let mut edges = BTreeMap::new();
    let mut owner = BTreeMap::new();
    for (index, root) in roots.iter().enumerate() {
        if let Ok(relative) = root.strip_prefix(repo) {
            let prefix = relative.to_string_lossy().replace('\\', "/");
            for path in &paths {
                if path.starts_with(&prefix) {
                    owner.insert(path.clone(), index);
                }
            }
        }
    }
    for document in documents {
        let base = Path::new(&document.path).parent().unwrap_or(Path::new(""));
        let mut targets = BTreeSet::new();
        for reference in &document.refs {
            let joined = lexical_path(&base.join(&reference.path));
            if paths.contains(&joined) {
                targets.insert((joined, reference.kind.clone()));
            }
        }
        edges.insert(document.path.clone(), targets);
    }
    (edges, owner)
}

fn distances(edges: &GraphEdges, from: &str, to: &str, undirected: bool) -> Option<usize> {
    let mut queue = VecDeque::from([(from.to_owned(), 0)]);
    let mut seen = BTreeSet::new();
    while let Some((node, depth)) = queue.pop_front() {
        if !seen.insert(node.clone()) {
            continue;
        }
        if node == to {
            return Some(depth);
        }
        let mut next = edges
            .get(&node)
            .into_iter()
            .flatten()
            .map(|(target, _)| target.clone())
            .collect::<BTreeSet<_>>();
        if undirected {
            for (source, targets) in edges {
                if targets.iter().any(|(target, _)| target == &node) {
                    next.insert(source.clone());
                }
            }
        }
        for next_node in next {
            queue.push_back((next_node, depth + 1));
        }
    }
    None
}
fn graph_class(
    edges: &GraphEdges,
    owner: &BTreeMap<String, usize>,
    a: &Chunk,
    b: &Chunk,
) -> GraphClass {
    let linked = |from: &str, to: &str| {
        edges
            .get(from)
            .is_some_and(|targets| targets.iter().any(|(target, _)| target == to))
    };
    let direct =
        linked(&a.endpoint.path, &b.endpoint.path) || linked(&b.endpoint.path, &a.endpoint.path);
    let directed = distances(edges, &a.endpoint.path, &b.endpoint.path, false)
        .or_else(|| distances(edges, &b.endpoint.path, &a.endpoint.path, false));
    let undirected = distances(edges, &a.endpoint.path, &b.endpoint.path, true);
    GraphClass {
        directly_linked: direct,
        directed_distance: directed,
        undirected_distance: undirected,
        same_component: undirected.is_some(),
        same_skill: owner
            .get(&a.endpoint.path)
            .zip(owner.get(&b.endpoint.path))
            .is_some_and(|(left, right)| left == right),
        disconnected: undirected.is_none(),
    }
}
fn endpoint_identity(chunk: &Chunk) -> String {
    serde_json::to_string(&(
        &chunk.endpoint.path,
        &chunk.endpoint.heading_path,
        chunk.endpoint.part,
        &chunk.endpoint.source_hash,
    ))
    .expect("endpoint identity is serializable")
}

fn identity(kind: &str, a: &Chunk, b: &Chunk, lock_digest: Option<&str>) -> String {
    let (left, right) = if a.endpoint <= b.endpoint {
        (a, b)
    } else {
        (b, a)
    };
    let model_identity = if kind == "semantic" {
        format!(
            ":{}",
            lock_digest.expect("semantic identity requires a model-lock digest")
        )
    } else {
        String::new()
    };
    digest(
        format!(
            "body:{kind}:{DETECTOR_VERSION}:{CHUNKER_VERSION}{model_identity}:{}:{}",
            endpoint_identity(left),
            endpoint_identity(right)
        )
        .as_bytes(),
    )
}

fn report_finding_with_disposition(finding: &Finding, disposition: &str) -> ReportFinding {
    let endpoint = |chunk: &Chunk| ReportEndpoint {
        path: chunk.endpoint.path.clone(),
        heading_path: chunk.endpoint.heading_path.clone(),
        part: chunk.endpoint.part,
        source_hash: chunk.endpoint.source_hash.clone(),
        span: chunk.endpoint.span.clone(),
        original_excerpt: chunk.original_excerpt.clone(),
        token_count: chunk.tokens,
    };
    ReportFinding {
        id: finding.id.clone(),
        lane: finding.lane.clone(),
        detector: finding.detector.clone(),
        kind: finding.kind.clone(),
        left: endpoint(&finding.left),
        right: endpoint(&finding.right),
        graph: finding.graph.clone(),
        cosine: finding.score,
        duplicate_tokens_estimate: finding.duplicate_tokens_estimate,
        disposition: disposition.into(),
    }
}

#[cfg(test)]
fn report_finding(finding: &Finding) -> ReportFinding {
    report_finding_with_disposition(finding, "unaccepted")
}

const SCORE_STRATA: [(f32, f32); 5] = [(-1.0, 0.5), (0.5, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.0)];

fn score_stratum(score: f32) -> usize {
    let score = score.clamp(-1.0, 1.0);
    SCORE_STRATA
        .iter()
        .position(|(min, max)| score >= *min && (score < *max || (*max == 1.0 && score <= *max)))
        .expect("score is clamped to the calibration strata")
}

fn sample_endpoint(endpoint: &ReportEndpoint) -> String {
    format!(
        "{}#{}#part-{}#{}",
        endpoint.path,
        endpoint.heading_path.join(" > "),
        endpoint.part,
        endpoint.source_hash
    )
}

fn calibration_data(findings: &[ReportFinding]) -> CalibrationData {
    let semantic = findings
        .iter()
        .filter(|finding| finding.kind == "semantic" && finding.cosine.is_some())
        .collect::<Vec<_>>();
    let mut counts = vec![0usize; SCORE_STRATA.len()];
    let mut selected = BTreeMap::<usize, &ReportFinding>::new();
    for finding in semantic {
        let stratum = score_stratum(finding.cosine.unwrap());
        counts[stratum] += 1;
        selected
            .entry(stratum)
            .and_modify(|current| {
                if finding.id < current.id {
                    *current = finding;
                }
            })
            .or_insert(finding);
    }
    CalibrationData {
        score_distribution: SCORE_STRATA
            .iter()
            .zip(counts)
            .map(|((min_score, max_score), count)| ScoreStratum {
                min_score: *min_score,
                max_score: *max_score,
                count,
            })
            .collect(),
        samples: selected
            .into_values()
            .map(|finding| Sample {
                left: sample_endpoint(&finding.left),
                right: sample_endpoint(&finding.right),
                score: finding.cosine.unwrap(),
                label: "review-required".into(),
            })
            .collect(),
    }
}

fn calibration_digest(calibration: &Calibration) -> Result<String, String> {
    serde_json::to_vec(calibration)
        .map(|bytes| digest(&bytes))
        .map_err(|error| error.to_string())
}

fn reviewed_calibration(calibration: &Calibration) -> Result<ReviewedCalibration, String> {
    Ok(ReviewedCalibration {
        digest: calibration_digest(calibration)?,
        thresholds: calibration.thresholds.clone(),
    })
}

fn graph_class_name(graph: &GraphClass) -> String {
    if graph.directly_linked {
        "directly-linked"
    } else if graph.same_skill {
        "same-skill"
    } else if graph.same_component {
        "connected"
    } else {
        "disconnected"
    }
    .into()
}

fn finding_disposition(finding: &Finding, baseline: Option<&Baseline>, block: f32) -> String {
    let blocking = finding.kind == "exact" || finding.score.is_some_and(|score| score >= block);
    if !blocking {
        return "advisory".into();
    }
    baseline
        .and_then(|baseline| baseline.findings.get(&finding.id))
        .map(|disposition| disposition.status.clone())
        .unwrap_or_else(|| "unaccepted".into())
}

fn duplicate_components<'a>(
    findings: impl IntoIterator<Item = &'a Finding>,
) -> Vec<DuplicateComponent> {
    let findings = findings.into_iter().collect::<Vec<_>>();
    let mut adjacency = BTreeMap::<String, BTreeSet<String>>::new();
    let mut tokens = BTreeMap::<String, usize>::new();
    let mut endpoints_by_finding = Vec::new();
    for finding in &findings {
        let left = endpoint_identity(&finding.left);
        let right = endpoint_identity(&finding.right);
        adjacency
            .entry(left.clone())
            .or_default()
            .insert(right.clone());
        adjacency
            .entry(right.clone())
            .or_default()
            .insert(left.clone());
        tokens.insert(left.clone(), finding.left.tokens);
        tokens.insert(right.clone(), finding.right.tokens);
        endpoints_by_finding.push((finding.id.clone(), left, right));
    }
    let mut visited = BTreeSet::new();
    let mut components = Vec::new();
    for root in adjacency.keys() {
        if !visited.insert(root.clone()) {
            continue;
        }
        let mut queue = VecDeque::from([root.clone()]);
        let mut endpoints = Vec::new();
        while let Some(endpoint) = queue.pop_front() {
            endpoints.push(endpoint.clone());
            for neighbor in adjacency.get(&endpoint).into_iter().flatten() {
                if visited.insert(neighbor.clone()) {
                    queue.push_back(neighbor.clone());
                }
            }
        }
        endpoints.sort();
        let endpoint_set = endpoints.iter().collect::<BTreeSet<_>>();
        let mut finding_ids = endpoints_by_finding
            .iter()
            .filter(|(_, left, right)| endpoint_set.contains(left) && endpoint_set.contains(right))
            .map(|(id, _, _)| id.clone())
            .collect::<Vec<_>>();
        finding_ids.sort();
        let member_tokens = endpoints
            .iter()
            .map(|endpoint| tokens.get(endpoint).copied().unwrap_or(0))
            .collect::<Vec<_>>();
        let redundant_tokens_estimate =
            member_tokens.iter().sum::<usize>() - member_tokens.iter().copied().max().unwrap_or(0);
        components.push(DuplicateComponent {
            id: digest(endpoints.join("\n").as_bytes()),
            endpoints,
            finding_ids,
            redundant_tokens_estimate,
        });
    }
    components
}

fn trends(classified: &[(Finding, String)], baseline: Option<&Baseline>) -> Trends {
    type Key = (String, String, String);
    let current_component_tokens = duplicate_components(
        classified
            .iter()
            .filter(|(_, disposition)| disposition != "advisory")
            .map(|(finding, _)| finding),
    )
    .into_iter()
    .filter_map(|component| {
        component
            .finding_ids
            .first()
            .cloned()
            .map(|id| (id, component.redundant_tokens_estimate))
    })
    .collect::<BTreeMap<_, _>>();
    let mut groups = BTreeMap::<Key, TrendAccumulator>::new();
    for (finding, disposition) in classified {
        let key = (
            finding.lane.clone(),
            graph_class_name(&finding.graph),
            disposition.clone(),
        );
        let accumulator = groups.entry(key).or_default();
        accumulator.current_findings += 1;
        accumulator.current_estimated_duplicate_tokens += current_component_tokens
            .get(&finding.id)
            .copied()
            .unwrap_or(0);
    }
    if let Some(baseline) = baseline {
        for disposition in baseline.findings.values() {
            let accumulator = groups
                .entry((
                    disposition.lane.clone(),
                    disposition.graph_class.clone(),
                    disposition.status.clone(),
                ))
                .or_default();
            accumulator.baseline_findings += 1;
            accumulator.baseline_estimated_duplicate_tokens +=
                disposition.component_tokens_estimate;
        }
    }
    Trends {
        groups: groups
            .into_iter()
            .map(
                |((lane, graph_class, disposition), accumulator)| TrendGroup {
                    lane,
                    graph_class,
                    disposition,
                    current_findings: accumulator.current_findings,
                    baseline_findings: accumulator.baseline_findings,
                    current_estimated_duplicate_tokens: accumulator
                        .current_estimated_duplicate_tokens,
                    baseline_estimated_duplicate_tokens: accumulator
                        .baseline_estimated_duplicate_tokens,
                },
            )
            .collect(),
    }
}

fn validate_analysis_mode(mode: Mode, has_calibration: bool) -> Result<(), String> {
    if matches!(mode, Mode::Calibrate) && has_calibration {
        Err("calibrate mode does not accept --calibration".into())
    } else {
        Ok(())
    }
}

fn analyze(args: AnalyzeArgs) -> Result<(), String> {
    validate_analysis_mode(args.mode, args.calibration.is_some())?;
    let lock = verify_model(&args.model_lock, &args.model_dir)?;
    let lock_digest = model_digest(&lock)?;
    let calibration = args
        .calibration
        .as_ref()
        .map(|path| read_yaml::<Calibration>(path))
        .transpose()?;
    let reviewed = if matches!(args.mode, Mode::Calibrate) {
        None
    } else {
        let calibration = calibration
            .as_ref()
            .ok_or("report/check requires calibration")?;
        validate_calibration(calibration, &lock_digest)?;
        Some(reviewed_calibration(calibration)?)
    };
    let baseline = if matches!(args.mode, Mode::Check) {
        let baseline =
            read_yaml::<Baseline>(args.baseline.as_ref().ok_or("check requires baseline")?)?;
        validate_baseline(&baseline, &lock_digest, reviewed.as_ref())?;
        Some(baseline)
    } else {
        None
    };
    let floor = calibration
        .as_ref()
        .map(|calibration| calibration.thresholds.review)
        .unwrap_or(-1.0);
    let block = calibration
        .as_ref()
        .map(|calibration| calibration.thresholds.block)
        .unwrap_or(1.0);

    let roots = load_roots(&args.repo, &args.manifest)?;
    let mut paths = Vec::new();
    for root in &roots {
        markdown_files(&args.repo, root, &mut paths)?;
    }
    paths.sort();
    let counter = model_token_counter(&args.model_dir)?;
    let docs = paths
        .iter()
        .map(|path| parse_document(path, &args.repo, &counter))
        .collect::<Result<Vec<_>, _>>()?;
    let (edges, owner) = graph(&docs, &roots, &args.repo);
    let mut findings = exact_findings(&docs, &counter, &edges, &owner)?;
    let chunks = chunks(&docs, &counter)?;
    let vectors = embed_payloads(
        &args.model_dir,
        &chunks
            .iter()
            .map(|chunk| chunk.payload.clone())
            .collect::<Vec<_>>(),
    )?;
    for (left_index, left) in chunks.iter().enumerate() {
        for (right_index, right) in chunks.iter().enumerate().skip(left_index + 1) {
            if !semantic_pair_eligible(left, right) {
                continue;
            }
            let score = cosine(&vectors[left_index], &vectors[right_index]);
            if score >= floor {
                findings.push(Finding {
                    id: identity("semantic", left, right, Some(&lock_digest)),
                    lane: "body".into(),
                    detector: DETECTOR_VERSION.into(),
                    kind: "semantic".into(),
                    left: left.clone(),
                    right: right.clone(),
                    graph: graph_class(&edges, &owner, left, right),
                    score: Some(score),
                    duplicate_tokens_estimate: left.tokens.min(right.tokens),
                });
            }
        }
    }
    let classified = findings
        .into_iter()
        .map(|finding| {
            let disposition = finding_disposition(&finding, baseline.as_ref(), block);
            (finding, disposition)
        })
        .collect::<Vec<_>>();
    let report_findings = classified
        .iter()
        .filter(|(_, disposition)| disposition != "intentional")
        .map(|(finding, disposition)| report_finding_with_disposition(finding, disposition))
        .collect::<Vec<_>>();
    let report_components = duplicate_components(
        classified
            .iter()
            .filter(|(_, disposition)| disposition != "intentional" && disposition != "advisory")
            .map(|(finding, _)| finding),
    );
    let report_calibration =
        matches!(args.mode, Mode::Calibrate).then(|| calibration_data(&report_findings));
    let report = Report {
        format: 1,
        detector: Detector {
            version: DETECTOR_VERSION.into(),
            model_lock_digest: lock_digest,
            chunker: CHUNKER_VERSION.into(),
            pooling: MODEL_POOLING.into(),
            normalization: MODEL_NORMALIZATION.into(),
        },
        mode: format!("{:?}", args.mode).to_lowercase(),
        trends: trends(&classified, baseline.as_ref()),
        findings: report_findings,
        duplicate_components: report_components,
        frontmatter: frontmatter_advisories(&roots)?,
        calibration: report_calibration,
        reviewed_calibration: reviewed,
    };
    fs::write(
        &args.json_out,
        serde_json::to_string_pretty(&report).map_err(|error| error.to_string())?,
    )
    .map_err(ioerr)?;
    fs::write(&args.markdown_out, markdown(&report)).map_err(ioerr)?;
    let blocked = classified
        .iter()
        .filter(|(_, disposition)| disposition == "unaccepted")
        .filter(|(finding, _)| {
            finding.kind == "exact" || finding.score.is_some_and(|score| score >= block)
        })
        .collect::<Vec<_>>();
    if matches!(args.mode, Mode::Check) && !blocked.is_empty() {
        return Err(format!(
            "new blocking overlap findings:\n{}",
            blocked
                .iter()
                .map(|(finding, _)| format!(
                    "- {} {} ↔ {}",
                    finding.kind, finding.left.endpoint.path, finding.right.endpoint.path
                ))
                .collect::<Vec<_>>()
                .join("\n")
        ));
    }
    Ok(())
}

fn frontmatter_advisories(roots: &[PathBuf]) -> Result<Vec<Advisory>, String> {
    let mut values = Vec::new();
    for root in roots {
        let file = root.join("SKILL.md");
        if let Ok(text) = fs::read_to_string(&file) {
            if let Some(frontmatter) = text.strip_prefix("---\n").and_then(|body| {
                body.split_once("\n---\n")
                    .map(|(frontmatter, _)| frontmatter)
            }) {
                let yaml: serde_yaml::Value = serde_yaml::from_str(frontmatter)
                    .map_err(|error| format!("{}: {error}", file.display()))?;
                for field in ["name", "description"] {
                    if let Some(value) = yaml.get(field).and_then(|value| value.as_str()) {
                        values.push(FrontmatterValue {
                            path: file.display().to_string(),
                            field: field.to_owned(),
                            value: value.to_owned(),
                        });
                    }
                }
            }
        }
    }
    let mut results = Vec::new();
    for (left_index, left_value) in values.iter().enumerate() {
        for right_value in values.iter().skip(left_index + 1) {
            if left_value.field == right_value.field {
                let score = lexical_strings(&left_value.value, &right_value.value);
                if score > 0.0 {
                    results.push(Advisory {
                        left: left_value.path.clone(),
                        right: right_value.path.clone(),
                        field: left_value.field.clone(),
                        left_value: left_value.value.clone(),
                        right_value: right_value.value.clone(),
                        score,
                    });
                }
            }
        }
    }
    Ok(results)
}
fn lexical_strings(left: &str, right: &str) -> f32 {
    let left_normalized = normalize(left);
    let right_normalized = normalize(right);
    let left_tokens: BTreeSet<_> = left_normalized.split_whitespace().collect();
    let right_tokens: BTreeSet<_> = right_normalized.split_whitespace().collect();
    if left_tokens.is_empty() || right_tokens.is_empty() {
        0.0
    } else {
        left_tokens.intersection(&right_tokens).count() as f32
            / ((left_tokens.len() * right_tokens.len()) as f32).sqrt()
    }
}
fn markdown(report: &Report) -> String {
    let mut out = format!("# Skill overlap report\n\nMode: `{}`\n\n", report.mode);
    out.push_str("## Trends\n\n| Lane | Graph class | Disposition | Current findings | Baseline findings | Current token estimate | Baseline token estimate |\n| --- | --- | --- | ---: | ---: | ---: | ---: |\n");
    for group in &report.trends.groups {
        out.push_str(&format!(
            "| {} | {} | {} | {} | {} | {} | {} |\n",
            group.lane,
            group.graph_class,
            group.disposition,
            group.current_findings,
            group.baseline_findings,
            group.current_estimated_duplicate_tokens,
            group.baseline_estimated_duplicate_tokens
        ));
    }
    out.push_str("\n## Duplicate components\n\n");
    if report.duplicate_components.is_empty() {
        out.push_str("No duplicate components.\n\n");
    }
    for component in &report.duplicate_components {
        out.push_str(&format!(
            "- `{}`: {} endpoints, {} findings, redundant-token estimate `{}`\n",
            component.id,
            component.endpoints.len(),
            component.finding_ids.len(),
            component.redundant_tokens_estimate
        ));
    }
    out.push('\n');
    if report.findings.is_empty() {
        out.push_str("No body overlap findings.\n");
    }
    for finding in &report.findings {
        out.push_str(&format!(
            "## Finding `{}`\n\n- Lane: `{}`\n- Detector: `{}`\n- Kind: `{}`\n- Disposition: `{}`\n",
            finding.id,
            finding.lane,
            finding.detector,
            finding.kind,
            finding.disposition
        ));
        for (side, endpoint) in [("Left", &finding.left), ("Right", &finding.right)] {
            out.push_str(&format!(
                "- {side}: `{}`; heading path `{}`; part `{}`; source hash `{}`; exact span `{}-{}`; token count `{}`\n",
                endpoint.path,
                endpoint.heading_path.join(" > "),
                endpoint.part,
                endpoint.source_hash,
                endpoint.span.start,
                endpoint.span.end,
                endpoint.token_count
            ));
        }
        out.push_str(&format!(
            "- Graph relation: directly linked `{}`, directed distance `{:?}`, undirected distance `{:?}`, same component `{}`, same skill `{}`, disconnected `{}`\n",
            finding.graph.directly_linked,
            finding.graph.directed_distance,
            finding.graph.undirected_distance,
            finding.graph.same_component,
            finding.graph.same_skill,
            finding.graph.disconnected
        ));
        if let Some(cosine) = finding.cosine {
            out.push_str(&format!("- Cosine: `{cosine:.6}`\n"));
        }
        out.push_str(&format!(
            "- Duplicate-token estimate: `{}`\n\n### Left original excerpt\n\n{}\n\n### Right original excerpt\n\n{}\n\n",
            finding.duplicate_tokens_estimate,
            indent_markdown(&finding.left.original_excerpt),
            indent_markdown(&finding.right.original_excerpt)
        ));
    }
    if let Some(calibration) = &report.calibration {
        out.push_str(
            "## Calibration\n\n| Minimum | Maximum | Semantic pairs |\n| ---: | ---: | ---: |\n",
        );
        for stratum in &calibration.score_distribution {
            out.push_str(&format!(
                "| {:.1} | {:.1} | {} |\n",
                stratum.min_score, stratum.max_score, stratum.count
            ));
        }
        out.push_str("\n### Review-required samples\n\n");
        for sample in &calibration.samples {
            out.push_str(&format!(
                "- `{}` ↔ `{}`: cosine `{:.6}`, label `{}`\n",
                sample.left, sample.right, sample.score, sample.label
            ));
        }
    }
    out.push_str("\n## Frontmatter advisories\n\n");
    if report.frontmatter.is_empty() {
        out.push_str("No frontmatter advisory pairs.\n");
    }
    for advisory in &report.frontmatter {
        out.push_str(&format!(
            "- `{}` ↔ `{}`\n  - Field: `{}`\n  - Score: `{:.6}`\n  - Left value: {:?}\n  - Right value: {:?}\n",
            advisory.left,
            advisory.right,
            advisory.field,
            advisory.score,
            advisory.left_value,
            advisory.right_value
        ));
    }
    out
}

fn indent_markdown(text: &str) -> String {
    text.lines()
        .map(|line| format!("    {line}"))
        .collect::<Vec<_>>()
        .join("\n")
}
fn validate_calibration(value: &Calibration, lock_digest: &str) -> Result<(), String> {
    if value.format != 1
        || value.status != "reviewed"
        || value.detector.version != DETECTOR_VERSION
        || value.detector.chunker != CHUNKER_VERSION
        || value.detector.model_lock_digest != lock_digest
        || value.detector.pooling != MODEL_POOLING
        || value.detector.normalization != MODEL_NORMALIZATION
        || !(0.0 <= value.thresholds.review
            && value.thresholds.review < value.thresholds.block
            && value.thresholds.block <= 1.0)
        || value.samples.is_empty()
        || value.samples.iter().any(|x| {
            !matches!(
                x.label.as_str(),
                "duplicate" | "intentional-repeat" | "related-not-duplicate" | "unrelated"
            )
        })
    {
        Err("calibration is incomplete or incompatible; explicitly recalibrate".into())
    } else {
        Ok(())
    }
}
fn validate_baseline(
    value: &Baseline,
    lock_digest: &str,
    calibration: Option<&ReviewedCalibration>,
) -> Result<(), String> {
    let digest_is_valid = Regex::new(r"^[a-f0-9]{64}$")
        .unwrap()
        .is_match(&value.calibration_digest);
    if value.format != 1
        || value.status != "reviewed"
        || value.detector.version != DETECTOR_VERSION
        || value.detector.chunker != CHUNKER_VERSION
        || value.detector.model_lock_digest != lock_digest
        || value.detector.pooling != MODEL_POOLING
        || value.detector.normalization != MODEL_NORMALIZATION
        || !digest_is_valid
        || !(0.0 < value.block_threshold && value.block_threshold <= 1.0)
    {
        return Err("baseline metadata is incompatible; explicitly rebaseline".into());
    }
    if calibration.is_some_and(|calibration| {
        value.calibration_digest != calibration.digest
            || value.block_threshold != calibration.thresholds.block
    }) {
        return Err(
            "baseline calibration digest or reviewed block threshold is incompatible; explicitly rebaseline"
                .into(),
        );
    }
    for (id, disposition) in &value.findings {
        if !matches!(disposition.status.as_str(), "intentional" | "debt")
            || disposition
                .reason
                .as_deref()
                .filter(|reason| !reason.trim().is_empty())
                .is_none()
            || disposition.lane.trim().is_empty()
            || !matches!(
                disposition.graph_class.as_str(),
                "directly-linked" | "same-skill" | "connected" | "disconnected"
            )
        {
            return Err(format!("baseline disposition {id} is incomplete"));
        }
    }
    Ok(())
}
fn candidate_calibration(report: Report) -> Result<Calibration, String> {
    let samples = report
        .calibration
        .ok_or("calibration prepare requires a calibrate-mode report")?
        .samples;
    Ok(Calibration {
        format: 1,
        status: "draft".into(),
        detector: report.detector,
        thresholds: Thresholds {
            review: 0.80,
            block: 0.90,
        },
        samples,
    })
}

fn calibration(command: CalibrationCommand) -> Result<(), String> {
    match command {
        CalibrationCommand::Prepare { report, out } => {
            let report: Report = read_json(&report)?;
            write_yaml(&out, &candidate_calibration(report)?)
        }
        CalibrationCommand::Validate {
            calibration,
            model_lock,
        } => {
            let value: Calibration = read_yaml(&calibration)?;
            validate_calibration(&value, &validated_model_digest(&model_lock)?)
        }
    }
}
fn baseline(command: BaselineCommand) -> Result<(), String> {
    match command {
        BaselineCommand::Prepare { report, out } => {
            let report: Report = read_json(&report)?;
            let reviewed = report
                .reviewed_calibration
                .ok_or("baseline prepare requires a report with reviewed calibration metadata")?;
            let component_tokens = report
                .duplicate_components
                .iter()
                .filter_map(|component| {
                    component
                        .finding_ids
                        .first()
                        .map(|id| (id.clone(), component.redundant_tokens_estimate))
                })
                .collect::<BTreeMap<_, _>>();
            let findings = report
                .findings
                .into_iter()
                .filter(|finding| {
                    finding.kind == "exact"
                        || finding
                            .cosine
                            .is_some_and(|score| score >= reviewed.thresholds.block)
                })
                .map(|finding| {
                    let graph_class = graph_class_name(&finding.graph);
                    let component_tokens_estimate =
                        component_tokens.get(&finding.id).copied().unwrap_or(0);
                    (
                        finding.id,
                        Disposition {
                            status: "review-required".into(),
                            reason: None,
                            issue: None,
                            lane: finding.lane,
                            graph_class,
                            duplicate_tokens_estimate: finding.duplicate_tokens_estimate,
                            component_tokens_estimate,
                        },
                    )
                })
                .collect();
            write_yaml(
                &out,
                &Baseline {
                    format: 1,
                    status: "draft".into(),
                    detector: report.detector,
                    calibration_digest: reviewed.digest,
                    block_threshold: reviewed.thresholds.block,
                    findings,
                },
            )
        }
        BaselineCommand::Validate {
            baseline,
            calibration,
            model_lock,
        } => {
            let lock_digest = validated_model_digest(&model_lock)?;
            let calibration: Calibration = read_yaml(&calibration)?;
            validate_calibration(&calibration, &lock_digest)?;
            let reviewed = reviewed_calibration(&calibration)?;
            let baseline: Baseline = read_yaml(&baseline)?;
            validate_baseline(&baseline, &lock_digest, Some(&reviewed))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{
        path::Path,
        sync::atomic::{AtomicU64, Ordering},
    };

    static TEMP_ID: AtomicU64 = AtomicU64::new(0);

    #[test]
    fn load_roots_rejects_absolute_manifest_paths() {
        let repo = temp_dir("absolute-root-repo");
        let outside = temp_dir("absolute-root-outside");
        let manifest = repo.join("manifest.json");
        fs::write(
            &manifest,
            serde_json::to_vec(&serde_json::json!({ "skills": [outside] })).unwrap(),
        )
        .unwrap();

        let error = load_roots(&repo, &manifest).unwrap_err();
        assert!(error.contains("relative"), "{error}");

        let _ = fs::remove_dir_all(repo);
        let _ = fs::remove_dir_all(outside);
    }

    #[test]
    fn load_roots_rejects_parent_manifest_paths() {
        let repo = temp_dir("parent-root-repo");
        let manifest = repo.join("manifest.json");
        fs::write(
            &manifest,
            serde_json::to_vec(&serde_json::json!({ "skills": ["../outside"] })).unwrap(),
        )
        .unwrap();

        let error = load_roots(&repo, &manifest).unwrap_err();
        assert!(error.contains("parent"), "{error}");

        let _ = fs::remove_dir_all(repo);
    }

    #[cfg(unix)]
    #[test]
    fn markdown_files_rejects_directory_symlink_escape() {
        let repo = temp_dir("directory-symlink-repo");
        let root = repo.join("skills/example");
        fs::create_dir_all(&root).unwrap();
        let outside = temp_dir("directory-symlink-outside");
        fs::write(outside.join("secret.md"), "secret").unwrap();
        std::os::unix::fs::symlink(&outside, root.join("escape")).unwrap();

        let mut paths = Vec::new();
        let error = markdown_files(&repo, &root, &mut paths).unwrap_err();
        assert!(error.contains("symlink"), "{error}");
        assert!(paths.is_empty());

        let _ = fs::remove_dir_all(repo);
        let _ = fs::remove_dir_all(outside);
    }

    #[cfg(unix)]
    #[test]
    fn markdown_files_rejects_markdown_symlink_escape() {
        let repo = temp_dir("file-symlink-repo");
        let root = repo.join("skills/example");
        fs::create_dir_all(&root).unwrap();
        let outside = temp_dir("file-symlink-outside");
        let secret = outside.join("secret.md");
        fs::write(&secret, "secret").unwrap();
        std::os::unix::fs::symlink(&secret, root.join("escape.md")).unwrap();

        let mut paths = Vec::new();
        let error = markdown_files(&repo, &root, &mut paths).unwrap_err();
        assert!(error.contains("symlink"), "{error}");
        assert!(paths.is_empty());

        let _ = fs::remove_dir_all(repo);
        let _ = fs::remove_dir_all(outside);
    }

    #[test]
    fn relative_refs_match_python_contract() {
        let cases: serde_json::Value =
            serde_json::from_str(include_str!("../fixtures/relative-md-refs.json")).unwrap();
        for case in cases.as_array().unwrap() {
            let expected = case["refs"]
                .as_array()
                .unwrap()
                .iter()
                .map(|value| value.as_str().unwrap().to_owned())
                .collect::<Vec<_>>();
            assert_eq!(
                extract_relative_refs(case["text"].as_str().unwrap()),
                expected,
                "{}",
                case["name"].as_str().unwrap()
            );
        }
    }

    #[test]
    fn relative_refs_preserve_edge_type() {
        assert_eq!(
            extract_typed_relative_refs("[Guide](references/a.md) and `../b/SKILL.md`"),
            vec![
                relative_ref("references/a.md", RefKind::MarkdownLink),
                relative_ref("../b/SKILL.md", RefKind::BacktickedPath),
            ]
        );
    }

    #[test]
    fn pointer_grammar_uses_actual_relative_reference_syntax() {
        let root = temp_path("pointers.md");
        fs::write(
            &root,
            "# Doc\n## Link\nSee [the guide](references/a.md).\n## Tick\nFull details in `references/b.md`!\n## Lives\nThe full contract lives in [the contract](../shared/SKILL.md).\n## Bare\nSee references/a.md.\n## Extra\nSee [the guide](references/a.md) and explain it.\n## List\n- See [the guide](references/a.md).\n## Two\nSee [one](references/a.md) and [two](references/b.md).\n",
        )
        .unwrap();
        let doc = parse_document(&root, root.parent().unwrap(), &TokenCounter::Test).unwrap();
        assert_eq!(
            doc.sections
                .iter()
                .map(|section| section.pointer)
                .collect::<Vec<_>>(),
            vec![true, true, true, false, false, false, false]
        );
        let _ = fs::remove_file(root);
    }

    #[test]
    fn wrapped_pointer_is_classified_after_whitespace_normalization() {
        let root = temp_path("wrapped-pointer.md");
        fs::write(
            &root,
            "# Doc\n## Wrapped\nSee [the\n guide](references/a.md).\n",
        )
        .unwrap();

        let doc = parse_document(&root, root.parent().unwrap(), &TokenCounter::Test).unwrap();
        assert!(doc.sections[0].pointer);

        let _ = fs::remove_file(root);
    }

    #[test]
    fn normalization_preserves_case_and_punctuation() {
        assert_eq!(normalize("A  B\r\nC"), "A B C");
        assert_ne!(normalize("A"), normalize("a"));
    }

    #[test]
    fn headings_in_fences_do_not_split() {
        let root = temp_path("fence.md");
        fs::write(&root, "# Doc\n## One\n```md\n## fake\n```\nbody\n").unwrap();
        let doc = parse_document(&root, root.parent().unwrap(), &TokenCounter::Test).unwrap();
        assert_eq!(doc.sections.len(), 1);
        assert_eq!(doc.sections[0].headings, vec!["Doc", "One"]);
        let _ = fs::remove_file(root);
    }

    #[test]
    fn fences_close_only_with_matching_marker_and_length() {
        for (name, text) in [
            (
                "short-backticks.md",
                "# Doc\n## One\n````md\n```\n## fake\n```\n````\n## Two\nbody\n",
            ),
            (
                "mixed-markers.md",
                "# Doc\n## One\n```md\n~~~\n## fake\n~~~\n```\n## Two\nbody\n",
            ),
        ] {
            let root = temp_path(name);
            fs::write(&root, text).unwrap();
            let doc = parse_document(&root, root.parent().unwrap(), &TokenCounter::Test).unwrap();
            assert_eq!(
                doc.sections
                    .iter()
                    .map(|section| section.headings.last().unwrap().as_str())
                    .collect::<Vec<_>>(),
                vec!["One", "Two"],
                "{name}"
            );
            let _ = fs::remove_file(root);
        }
    }

    #[test]
    fn fence_closers_require_commonmark_indent_and_blank_suffix() {
        for (name, invalid_closer) in [
            ("trailing-text.md", "```not-a-closer"),
            ("four-space-indent.md", "    ```"),
        ] {
            let root = temp_path(name);
            fs::write(
                &root,
                format!(
                    "# Doc\n## One\n```md\n{invalid_closer}\n## fake\n``` \t\n## Two\nbody\n"
                ),
            )
            .unwrap();
            let doc = parse_document(&root, root.parent().unwrap(), &TokenCounter::Test).unwrap();
            assert_eq!(
                doc.sections
                    .iter()
                    .map(|section| section.headings.last().unwrap().as_str())
                    .collect::<Vec<_>>(),
                vec!["One", "Two"],
                "{name}"
            );
            let _ = fs::remove_file(root);
        }
    }

    #[test]
    fn parse_to_chunk_keeps_body_line_spans() {
        let root = temp_path("spans.md");
        fs::write(&root, "# Doc\n## One\nfirst\nsecond\n### Two\nthird\n").unwrap();
        let doc = parse_document(&root, root.parent().unwrap(), &TokenCounter::Test).unwrap();
        assert_eq!(doc.sections[0].span, Span { start: 3, end: 4 });
        assert_eq!(doc.sections[1].span, Span { start: 6, end: 6 });
        let chunks = chunks(&[doc], &TokenCounter::Test).unwrap();
        assert_eq!(chunks[0].endpoint.span, Span { start: 3, end: 4 });
        assert_eq!(chunks[1].endpoint.span, Span { start: 6, end: 6 });
        let _ = fs::remove_file(root);
    }

    #[test]
    fn oversized_sections_split_with_exact_source_spans() {
        let source_lines = (0..500).map(|n| format!("word{n}")).collect::<Vec<_>>();
        let section = test_section(
            "x.md",
            &["Doc", "Long"],
            Span {
                start: 10,
                end: 509,
            },
            &source_lines.join("\n"),
        );
        let pieces = split_section(&section, 2, &TokenCounter::Test).unwrap();
        assert!(pieces.len() > 1);
        let mut next_start = 10;
        for piece in &pieces {
            assert_eq!(piece.span.start, next_start);
            assert_eq!(
                piece.body,
                source_lines[piece.span.start - 10..=piece.span.end - 10].join("\n")
            );
            next_start = piece.span.end + 1;
        }
        assert_eq!(next_start, 510);
        assert!(pieces
            .iter()
            .all(|piece| piece.body.split_whitespace().count() + 2 <= 480));
    }

    #[test]
    fn structural_split_prefers_h4_before_the_target() {
        let mut lines = (0..350).map(|n| format!("before{n}")).collect::<Vec<_>>();
        lines.push("#### Detail".into());
        lines.extend((0..150).map(|n| format!("after{n}")));
        let section = test_section(
            "x.md",
            &["Doc"],
            Span {
                start: 10,
                end: 510,
            },
            &lines.join("\n"),
        );
        let pieces = split_section(&section, 1, &TokenCounter::Test).unwrap();
        assert_eq!(
            pieces[0].span,
            Span {
                start: 10,
                end: 359
            }
        );
        assert!(pieces[1].body.starts_with("#### Detail"));
    }

    #[test]
    fn fixed_windows_keep_the_source_line_span() {
        let section = test_section(
            "x.md",
            &["Doc"],
            Span { start: 10, end: 10 },
            &(0..500)
                .map(|n| format!("word{n}"))
                .collect::<Vec<_>>()
                .join(" "),
        );
        let pieces = split_section(&section, 1, &TokenCounter::Test).unwrap();
        assert!(pieces.len() > 1);
        assert!(pieces
            .iter()
            .all(|piece| piece.span == Span { start: 10, end: 10 }));
    }

    #[test]
    fn fixed_windows_split_one_oversized_source_unit() {
        let pieces = fixed_token_windows(&"x".repeat(25), 10, &TokenCounter::TestChars).unwrap();
        assert_eq!(pieces.concat(), "x".repeat(25));
        assert_eq!(pieces.iter().map(String::len).collect::<Vec<_>>(), vec![10, 10, 5]);
    }

    #[test]
    fn structural_split_keeps_list_children_with_their_item() {
        let mut lines = (0..350).map(|n| format!("before{n}")).collect::<Vec<_>>();
        lines.push("- parent".into());
        lines.extend((0..30).map(|n| format!("  child{n}")));
        lines.extend((0..150).map(|n| format!("after{n}")));
        let section = test_section(
            "x.md",
            &["Doc"],
            Span {
                start: 1,
                end: lines.len(),
            },
            &lines.join("\n"),
        );
        let pieces = split_section(&section, 1, &TokenCounter::Test).unwrap();
        let list_piece = pieces
            .iter()
            .find(|piece| piece.body.contains("- parent"))
            .unwrap();
        assert!(list_piece.body.contains("  child29"));
    }

    #[test]
    fn oversized_list_group_falls_back_to_targeted_source_line_cuts() {
        let mut lines = vec!["- parent".to_owned()];
        lines.extend((0..500).map(|n| format!("  child{n}")));
        let section = test_section(
            "x.md",
            &["Doc"],
            Span {
                start: 10,
                end: 510,
            },
            &lines.join("\n"),
        );

        let pieces = split_section(&section, 2, &TokenCounter::Test).unwrap();

        assert_eq!(pieces.len(), 2);
        assert_eq!(
            pieces[0].body.split_whitespace().count() + 2,
            384,
            "fallback still targets the preferred payload size"
        );
        assert_eq!(
            pieces[0].span,
            Span {
                start: 10,
                end: 390
            }
        );
        assert_eq!(
            pieces[1].span,
            Span {
                start: 391,
                end: 510
            }
        );
        assert!(pieces
            .iter()
            .all(|piece| piece.body.split_whitespace().count() + 2 <= 480));
    }

    #[test]
    fn structural_split_uses_sentence_before_fixed_window() {
        let first = (0..300)
            .map(|n| format!("first{n}"))
            .collect::<Vec<_>>()
            .join(" ");
        let second = (0..250)
            .map(|n| format!("second{n}"))
            .collect::<Vec<_>>()
            .join(" ");
        let section = test_section(
            "x.md",
            &["Doc"],
            Span { start: 10, end: 10 },
            &format!("{first}. {second}."),
        );
        let pieces = split_section(&section, 1, &TokenCounter::Test).unwrap();
        assert!(pieces[0].body.ends_with('.'));
        assert!(pieces[1].body.starts_with("second0"));
    }

    #[test]
    fn repeated_table_header_is_payload_only() {
        let mut rows = vec!["| Name | Value |".into(), "| --- | --- |".into()];
        rows.extend((0..300).map(|n| format!("| row{n} | value{n} |")));
        let section = test_section(
            "table.md",
            &["Doc", "Table"],
            Span {
                start: 10,
                end: 311,
            },
            &rows.join("\n"),
        );
        let document = Document {
            path: "table.md".into(),
            refs: vec![],
            sections: vec![section],
        };
        let chunks = chunks(&[document], &TokenCounter::Test).unwrap();
        let repeated = chunks
            .iter()
            .skip(1)
            .find(|chunk| chunk.payload.contains("| Name | Value |"))
            .unwrap();
        assert!(!repeated.evidence.contains("Name"));
        assert!(!repeated.original_excerpt.contains("Name"));
        assert_eq!(
            repeated.tokens,
            repeated.original_excerpt.split_whitespace().count()
        );
    }

    #[test]
    fn h3_identity_keeps_h2_parent_and_h4_is_body_only() {
        let root = temp_path("heading-identity.md");
        fs::write(
            &root,
            "# Doc\n## Parent\nparent body\n### Child\nchild body\n#### Detail\ndetail body\n",
        )
        .unwrap();
        let doc = parse_document(&root, root.parent().unwrap(), &TokenCounter::Test).unwrap();
        assert_eq!(doc.sections[0].headings, vec!["Doc", "Parent"]);
        assert_eq!(doc.sections[1].headings, vec!["Doc", "Parent", "Child"]);
        assert!(doc.sections[1].body.contains("#### Detail"));
        let chunks = chunks(&[doc], &TokenCounter::Test).unwrap();
        assert_eq!(chunks[0].endpoint.heading_path, vec!["Doc", "Parent"]);
        assert_eq!(
            chunks[1].endpoint.heading_path,
            vec!["Doc", "Parent", "Child"]
        );
        let _ = fs::remove_file(root);
    }

    #[test]
    fn graph_reads_intro_references_and_preserves_both_edge_types() {
        let repo = temp_dir("intro-graph");
        let a = repo.join("a.md");
        let references = repo.join("references");
        let b = references.join("b.md");
        fs::create_dir(&references).unwrap();
        fs::write(&a, "# A\n[B](references/b.md) and `references/b.md`\n").unwrap();
        fs::write(&b, "# B\n").unwrap();
        let documents = vec![
            parse_document(&a, &repo, &TokenCounter::Test).unwrap(),
            parse_document(&b, &repo, &TokenCounter::Test).unwrap(),
        ];
        let (edges, _) = graph(&documents, &[], &repo);
        assert_eq!(
            edges["a.md"],
            BTreeSet::from([
                ("references/b.md".into(), RefKind::MarkdownLink),
                ("references/b.md".into(), RefKind::BacktickedPath),
            ])
        );
        let _ = fs::remove_dir_all(repo);
    }

    #[test]
    fn exact_detection_includes_pointer_sections_and_same_file_sections() {
        let mut left = test_section(
            "same.md",
            &["Doc", "One"],
            Span { start: 3, end: 3 },
            "See `references/shared.md`.",
        );
        left.refs = extract_typed_relative_refs(&left.body);
        left.pointer = pointer_only(&left.body, &left.refs, &TokenCounter::Test).unwrap();
        let mut right = left.clone();
        right.headings = vec!["Doc".into(), "Two".into()];
        right.span = Span { start: 6, end: 6 };
        let documents = vec![Document {
            path: "same.md".into(),
            refs: left.refs.clone(),
            sections: vec![left, right],
        }];
        let findings = exact_findings(
            &documents,
            &TokenCounter::Test,
            &BTreeMap::new(),
            &BTreeMap::new(),
        )
        .unwrap();
        assert_eq!(findings.len(), 1);
        assert_eq!(findings[0].kind, "exact");
    }

    #[test]
    fn semantic_pairs_exclude_generated_parts_and_exact_duplicates() {
        let first = test_chunk("a.md", &["Doc", "One"], 1, "same");
        let mut generated_part = first.clone();
        generated_part.endpoint.part = 2;
        generated_part.endpoint.span = Span { start: 2, end: 2 };
        assert!(!semantic_pair_eligible(&first, &generated_part));

        let exact_other_section = test_chunk("b.md", &["Doc", "Two"], 1, "same");
        assert!(!semantic_pair_eligible(&first, &exact_other_section));
        let distinct = test_chunk("b.md", &["Doc", "Two"], 1, "different");
        assert!(semantic_pair_eligible(&first, &distinct));
    }

    #[test]
    fn parent_relative_graph_reference_is_directly_linked() {
        let documents = vec![
            Document {
                path: "skills/a/SKILL.md".into(),
                refs: vec![relative_ref("../b/SKILL.md", RefKind::BacktickedPath)],
                sections: vec![],
            },
            Document {
                path: "skills/b/SKILL.md".into(),
                refs: vec![],
                sections: vec![],
            },
        ];
        let roots = vec![PathBuf::from("skills/a"), PathBuf::from("skills/b")];
        let (edges, owner) = graph(&documents, &roots, Path::new(""));
        let left = test_chunk("skills/a/SKILL.md", &["A", "Body"], 1, "a");
        let right = test_chunk("skills/b/SKILL.md", &["B", "Body"], 1, "b");
        assert!(graph_class(&edges, &owner, &left, &right).directly_linked);
    }

    #[test]
    fn identity_uses_complete_unordered_endpoint_identity() {
        let base = test_chunk("skills/a/SKILL.md", &["Doc", "One"], 1, "same");
        let other = test_chunk("skills/b/SKILL.md", &["Doc", "Other"], 1, "other");
        let changed_heading = test_chunk("skills/a/SKILL.md", &["Doc", "Two"], 1, "same");
        let changed_part = test_chunk("skills/a/SKILL.md", &["Doc", "One"], 2, "same");
        let id = identity("semantic", &base, &other, Some("lock"));
        assert_ne!(
            id,
            identity("semantic", &changed_heading, &other, Some("lock"))
        );
        assert_ne!(
            id,
            identity("semantic", &changed_part, &other, Some("lock"))
        );
        assert_eq!(id, identity("semantic", &other, &base, Some("lock")));
    }

    #[test]
    fn exact_identity_ignores_model_lock_while_semantic_identity_tracks_it() {
        let left = test_chunk("skills/a/SKILL.md", &["Doc", "One"], 1, "left");
        let right = test_chunk("skills/b/SKILL.md", &["Doc", "Two"], 1, "right");

        assert_eq!(
            identity("exact", &left, &right, Some("first-lock")),
            identity("exact", &left, &right, Some("second-lock"))
        );
        assert_ne!(
            identity("semantic", &left, &right, Some("first-lock")),
            identity("semantic", &left, &right, Some("second-lock"))
        );
    }

    #[test]
    fn model_lock_rejects_unsafe_and_incomplete_artifact_sets() {
        assert!(validate_model_lock(&valid_lock()).is_ok());
        let mut pooling = valid_lock();
        pooling.pooling = "mean".into();
        assert!(validate_model_lock(&pooling).is_err());
        let mut normalization = valid_lock();
        normalization.normalization = "none".into();
        assert!(validate_model_lock(&normalization).is_err());
        for unsafe_path in [
            "../config.json",
            "/config.json",
            "./config.json",
            "onnx/../model.onnx",
        ] {
            let mut lock = valid_lock();
            lock.artifacts[0].path = unsafe_path.into();
            assert!(validate_model_lock(&lock)
                .unwrap_err()
                .contains("unsafe model artifact path"));
        }
        let mut duplicate = valid_lock();
        duplicate.artifacts[1].path = "config.json".into();
        assert!(validate_model_lock(&duplicate)
            .unwrap_err()
            .contains("duplicate model artifact"));
        let mut missing = valid_lock();
        missing.artifacts.pop();
        assert!(validate_model_lock(&missing)
            .unwrap_err()
            .contains("model artifact set mismatch"));
        let mut unexpected = valid_lock();
        unexpected.artifacts.push(Artifact {
            path: "extra.json".into(),
            sha256: "0".repeat(64),
        });
        assert!(validate_model_lock(&unexpected)
            .unwrap_err()
            .contains("model artifact set mismatch"));
    }

    #[test]
    fn parity_fixture_requires_locked_ubuntu_provenance() {
        let valid = serde_json::json!({
            "hallouminate": {
                "tag": PARITY_TAG,
                "commit": PARITY_COMMIT,
                "source_path": PARITY_SOURCE_PATH,
                "runner": PARITY_RUNNER,
                "execution_provider": PARITY_EXECUTION_PROVIDER,
                "threads": 1,
                "pooling": MODEL_POOLING,
                "normalization": MODEL_NORMALIZATION
            },
            "model_lock_digest": "lock",
            "cases": [{"input": "case", "output": vec![0.0; 384]}]
        });
        assert!(validate_fixture_provenance(&valid, "lock").is_ok());
        for pointer in [
            "/hallouminate/tag",
            "/hallouminate/commit",
            "/hallouminate/source_path",
            "/hallouminate/runner",
            "/hallouminate/execution_provider",
            "/hallouminate/threads",
            "/model_lock_digest",
            "/cases/0/input",
            "/cases/0/output",
        ] {
            let mut missing = valid.clone();
            missing.pointer_mut(pointer).unwrap().take();
            assert!(
                validate_fixture_provenance(&missing, "lock").is_err(),
                "accepted missing required provenance at {pointer}"
            );
        }
        let mut corrupt_output = valid.clone();
        corrupt_output["cases"][0]["output"] = serde_json::json!(vec!["invalid"; 384]);
        assert!(validate_fixture_provenance(&corrupt_output, "lock").is_err());
        for (field, value) in [("pooling", "mean"), ("normalization", "none")] {
            let mut drifted = valid.clone();
            drifted["hallouminate"][field] = value.into();
            assert!(validate_fixture_provenance(&drifted, "lock").is_err());
        }

        let checked_in: serde_json::Value =
            serde_json::from_str(include_str!("../fixtures/hallouminate-fastembed.json")).unwrap();
        let checked_in_lock: ModelLock =
            serde_json::from_str(include_str!("../model.lock.json")).unwrap();
        assert_eq!(checked_in["hallouminate"]["runner"], PARITY_RUNNER);
        assert_eq!(checked_in["hallouminate"]["threads"], 1);
        assert_eq!(checked_in["hallouminate"]["pooling"], MODEL_POOLING);
        assert_eq!(
            checked_in["hallouminate"]["normalization"],
            MODEL_NORMALIZATION
        );
        let lock_digest = model_digest(&checked_in_lock).unwrap();
        assert_eq!(checked_in["model_lock_digest"], lock_digest);
        assert!(validate_fixture_provenance(&checked_in, &lock_digest).is_ok());
    }

    #[test]
    fn dispositions_and_trends_retain_intentional_and_debt_history() {
        let intentional = test_finding("intentional-id", "exact", None, 7);
        let debt = test_finding("debt-id", "semantic", Some(0.95), 11);
        let baseline = Baseline {
            format: 1,
            status: "reviewed".into(),
            detector: detector("lock"),
            calibration_digest: "a".repeat(64),
            block_threshold: 0.9,
            findings: BTreeMap::from([
                (intentional.id.clone(), disposition("intentional", 7)),
                (debt.id.clone(), disposition("debt", 11)),
            ]),
        };
        assert_eq!(
            finding_disposition(&intentional, Some(&baseline), 0.9),
            "intentional"
        );
        assert_eq!(finding_disposition(&debt, Some(&baseline), 0.9), "debt");
        let classified = vec![(intentional, "intentional".into()), (debt, "debt".into())];
        let trends = trends(&classified, Some(&baseline));
        let intentional = trends
            .groups
            .iter()
            .find(|group| group.disposition == "intentional")
            .unwrap();
        assert_eq!(
            (intentional.current_findings, intentional.baseline_findings),
            (1, 1)
        );
        assert_eq!(
            (
                intentional.current_estimated_duplicate_tokens,
                intentional.baseline_estimated_duplicate_tokens
            ),
            (7, 7)
        );
    }

    #[test]
    fn duplicate_clique_uses_one_component_estimate() {
        let mut a = test_chunk("a.md", &["Doc", "A"], 1, "a");
        let mut b = test_chunk("b.md", &["Doc", "B"], 1, "b");
        let mut c = test_chunk("c.md", &["Doc", "C"], 1, "c");
        a.tokens = 10;
        b.tokens = 20;
        c.tokens = 30;
        let pair = |id: &str, left: Chunk, right: Chunk| {
            let mut finding = test_finding(id, "exact", None, left.tokens.min(right.tokens));
            finding.left = left;
            finding.right = right;
            finding
        };
        let findings = vec![
            pair("ab", a.clone(), b.clone()),
            pair("ac", a, c.clone()),
            pair("bc", b, c),
        ];
        let components = duplicate_components(findings.iter());
        assert_eq!(components.len(), 1);
        assert_eq!(components[0].redundant_tokens_estimate, 30);
        assert_eq!(components[0].finding_ids, vec!["ab", "ac", "bc"]);
        let classified = findings
            .into_iter()
            .map(|finding| (finding, "unaccepted".into()))
            .collect::<Vec<_>>();
        let trend = trends(&classified, None).groups.pop().unwrap();
        assert_eq!(trend.current_estimated_duplicate_tokens, 30);
        let json = serde_json::to_value(&components[0]).unwrap();
        assert_eq!(json["redundant_tokens_estimate"], 30);
    }

    #[test]
    fn mixed_group_component_trends_match_baseline_assignment() {
        let mut left = test_chunk("a.md", &["Doc", "A"], 1, "a");
        let mut middle = test_chunk("b.md", &["Doc", "B"], 1, "b");
        let mut right = test_chunk("c.md", &["Doc", "C"], 1, "c");
        left.tokens = 10;
        middle.tokens = 20;
        right.tokens = 30;
        let mut first = test_finding("first", "exact", None, 10);
        first.left = left;
        first.right = middle.clone();
        first.graph.directly_linked = true;
        let mut second = test_finding("second", "exact", None, 20);
        second.left = middle;
        second.right = right;
        let classified = vec![(first, "debt".into()), (second, "unaccepted".into())];
        let trends = trends(&classified, None);
        assert_eq!(
            trends
                .groups
                .iter()
                .map(|group| group.current_estimated_duplicate_tokens)
                .sum::<usize>(),
            30
        );
        assert_eq!(
            trends
                .groups
                .iter()
                .find(|group| group.disposition == "debt")
                .unwrap()
                .current_estimated_duplicate_tokens,
            30
        );
    }

    #[test]
    fn report_serialization_and_markdown_preserve_finding_evidence() {
        let mut finding = test_finding("stable-id", "semantic", Some(0.875), 7);
        finding.left.endpoint.path = "skills/a/SKILL.md".into();
        finding.left.endpoint.heading_path = vec!["Doc".into(), "Parent".into(), "Left".into()];
        finding.left.endpoint.part = 2;
        finding.left.endpoint.source_hash = "left-hash".into();
        finding.left.endpoint.span = Span { start: 10, end: 12 };
        finding.left.original_excerpt = "left original\nline two".into();
        finding.left.tokens = 7;
        finding.right.endpoint.path = "skills/b/SKILL.md".into();
        finding.right.endpoint.source_hash = "right-hash".into();
        finding.right.endpoint.span = Span { start: 20, end: 24 };
        finding.right.original_excerpt = "right original".into();
        finding.right.tokens = 11;
        finding.graph.directly_linked = true;
        finding.graph.directed_distance = Some(1);
        finding.graph.undirected_distance = Some(1);
        finding.graph.same_component = true;
        finding.graph.disconnected = false;
        let finding = report_finding_with_disposition(&finding, "debt");
        let json = serde_json::to_value(&finding).unwrap();
        assert_eq!(json["disposition"], "debt");
        assert_eq!(json["left"]["span"]["start"], 10);
        assert_eq!(json["left"]["original_excerpt"], "left original\nline two");
        assert_eq!(json["graph"]["directly_linked"], true);
        assert_eq!(json["cosine"], 0.875);
        assert_eq!(
            serde_json::from_value::<ReportFinding>(json).unwrap(),
            finding
        );

        let report = Report {
            format: 1,
            detector: detector("lock"),
            mode: "report".into(),
            findings: vec![finding],
            duplicate_components: vec![DuplicateComponent {
                id: "component-id".into(),
                endpoints: vec!["left".into(), "right".into()],
                finding_ids: vec!["stable-id".into()],
                redundant_tokens_estimate: 7,
            }],
            frontmatter: vec![Advisory {
                left: "skills/frontmatter-a/SKILL.md".into(),
                right: "skills/frontmatter-b/SKILL.md".into(),
                field: "description".into(),
                left_value: "Build cheese".into(),
                right_value: "Build aged cheese".into(),
                score: 0.75,
            }],
            trends: Trends {
                groups: vec![TrendGroup {
                    lane: "body".into(),
                    graph_class: "directly-linked".into(),
                    disposition: "debt".into(),
                    current_findings: 1,
                    baseline_findings: 1,
                    current_estimated_duplicate_tokens: 7,
                    baseline_estimated_duplicate_tokens: 7,
                }],
            },
            calibration: None,
            reviewed_calibration: None,
        };
        let rendered = markdown(&report);
        for evidence in [
            "stable-id",
            "Disposition: `debt`",
            "skills/a/SKILL.md",
            "Doc > Parent > Left",
            "part `2`",
            "left-hash",
            "exact span `10-12`",
            "left original",
            "right original",
            "directly linked `true`",
            "Cosine: `0.875000`",
            "Duplicate-token estimate: `7`",
            "| body | directly-linked | debt | 1 | 1 | 7 | 7 |",
            "redundant-token estimate `7`",
            "## Frontmatter advisories",
            "skills/frontmatter-a/SKILL.md",
            "skills/frontmatter-b/SKILL.md",
            "Field: `description`",
            "Score: `0.750000`",
            "Left value: \"Build cheese\"",
            "Right value: \"Build aged cheese\"",
        ] {
            assert!(
                rendered.contains(evidence),
                "missing Markdown evidence: {evidence}"
            );
        }
    }

    #[test]
    fn calibration_is_stratified_deterministic_and_review_required() {
        let mut findings = vec![
            scored_report_finding("z-low", "semantic", Some(0.2)),
            scored_report_finding("z-mid", "semantic", Some(0.55)),
            scored_report_finding("a-mid", "semantic", Some(0.56)),
            scored_report_finding("z-related", "semantic", Some(0.75)),
            scored_report_finding("z-review", "semantic", Some(0.85)),
            scored_report_finding("z-block", "semantic", Some(0.95)),
            scored_report_finding("exact-is-excluded", "exact", None),
        ];
        let data = calibration_data(&findings);
        assert_eq!(
            data.score_distribution
                .iter()
                .map(|stratum| stratum.count)
                .collect::<Vec<_>>(),
            vec![1, 2, 1, 1, 1]
        );
        assert_eq!(data.samples.len(), 5);
        assert!(data
            .samples
            .iter()
            .all(|sample| sample.label == "review-required"));
        assert_eq!(
            data.samples
                .iter()
                .map(|sample| score_stratum(sample.score))
                .collect::<BTreeSet<_>>(),
            BTreeSet::from([0, 1, 2, 3, 4])
        );
        findings.reverse();
        assert_eq!(calibration_data(&findings).samples, data.samples);

        let expected_samples = data.samples.clone();
        let candidate = candidate_calibration(Report {
            format: 1,
            detector: detector("lock"),
            mode: "calibrate".into(),
            findings,
            duplicate_components: vec![],
            frontmatter: vec![],
            trends: Trends { groups: vec![] },
            calibration: Some(data),
            reviewed_calibration: None,
        })
        .unwrap();
        assert_eq!(candidate.samples, expected_samples);
    }

    #[test]
    fn reviewed_preprocessing_metadata_rejects_drift() {
        let mut calibration = Calibration {
            format: 1,
            status: "reviewed".into(),
            detector: detector("lock"),
            thresholds: Thresholds {
                review: 0.8,
                block: 0.9,
            },
            samples: vec![Sample {
                left: "left".into(),
                right: "right".into(),
                score: 0.95,
                label: "duplicate".into(),
            }],
        };
        assert!(validate_calibration(&calibration, "lock").is_ok());
        calibration.detector.pooling = "mean".into();
        assert!(validate_calibration(&calibration, "lock").is_err());
        calibration.detector = detector("lock");
        calibration.detector.normalization = "none".into();
        assert!(validate_calibration(&calibration, "lock").is_err());

        let mut baseline = Baseline {
            format: 1,
            status: "reviewed".into(),
            detector: detector("lock"),
            calibration_digest: "a".repeat(64),
            block_threshold: 0.9,
            findings: BTreeMap::new(),
        };
        assert!(validate_baseline(&baseline, "lock", None).is_ok());
        baseline.detector.pooling = "mean".into();
        assert!(validate_baseline(&baseline, "lock", None).is_err());
        baseline.detector = detector("lock");
        baseline.detector.normalization = "none".into();
        assert!(validate_baseline(&baseline, "lock", None).is_err());
    }

    #[test]
    fn calibration_rejects_incompatible_format() {
        let calibration = Calibration {
            format: 2,
            status: "reviewed".into(),
            detector: detector("lock"),
            thresholds: Thresholds {
                review: 0.8,
                block: 0.9,
            },
            samples: vec![Sample {
                left: "left".into(),
                right: "right".into(),
                score: 0.95,
                label: "duplicate".into(),
            }],
        };
        assert!(validate_calibration(&calibration, "lock")
            .unwrap_err()
            .contains("explicitly recalibrate"));
    }

    #[test]
    fn calibrate_mode_rejects_prior_calibration_before_model_access() {
        assert!(validate_analysis_mode(Mode::Calibrate, false).is_ok());
        assert!(validate_analysis_mode(Mode::Report, true).is_ok());
        assert!(validate_analysis_mode(Mode::Calibrate, true)
            .unwrap_err()
            .contains("does not accept --calibration"));
    }

    #[test]
    fn baseline_prepare_uses_reviewed_block_threshold_and_keeps_evidence() {
        let report_path = temp_path("baseline-report.json");
        let baseline_path = temp_path("baseline.yml");
        let report = Report {
            format: 1,
            detector: detector("lock"),
            mode: "report".into(),
            findings: vec![
                scored_report_finding("below", "semantic", Some(0.92)),
                scored_report_finding("above", "semantic", Some(0.96)),
                scored_report_finding("exact", "exact", None),
            ],
            duplicate_components: vec![],
            frontmatter: vec![],
            trends: Trends { groups: vec![] },
            calibration: None,
            reviewed_calibration: Some(ReviewedCalibration {
                digest: "b".repeat(64),
                thresholds: Thresholds {
                    review: 0.8,
                    block: 0.95,
                },
            }),
        };
        fs::write(&report_path, serde_json::to_string(&report).unwrap()).unwrap();
        baseline(BaselineCommand::Prepare {
            report: report_path.clone(),
            out: baseline_path.clone(),
        })
        .unwrap();
        let prepared: Baseline = read_yaml(&baseline_path).unwrap();
        assert_eq!(prepared.block_threshold, 0.95);
        assert_eq!(prepared.calibration_digest, "b".repeat(64));
        assert!(!prepared.findings.contains_key("below"));
        assert!(prepared.findings.contains_key("above"));
        assert!(prepared.findings.contains_key("exact"));
        assert_eq!(prepared.findings["above"].lane, "body");
        assert_eq!(prepared.findings["above"].duplicate_tokens_estimate, 1);
        let _ = fs::remove_file(report_path);
        let _ = fs::remove_file(baseline_path);
    }

    #[test]
    fn baseline_rejects_incompatible_reviewed_calibration() {
        let baseline = Baseline {
            format: 1,
            status: "reviewed".into(),
            detector: detector("lock"),
            calibration_digest: "a".repeat(64),
            block_threshold: 0.9,
            findings: BTreeMap::new(),
        };
        let reviewed = ReviewedCalibration {
            digest: "b".repeat(64),
            thresholds: Thresholds {
                review: 0.8,
                block: 0.9,
            },
        };
        assert!(validate_baseline(&baseline, "lock", Some(&reviewed))
            .unwrap_err()
            .contains("explicitly rebaseline"));
    }

    #[test]
    fn validation_commands_reject_stale_model_metadata() {
        let model_lock_path = temp_path("model.lock.json");
        let calibration_path = temp_path("calibration.yml");
        let baseline_path = temp_path("baseline.yml");
        let lock = valid_lock();
        let lock_digest = model_digest(&lock).unwrap();
        fs::write(&model_lock_path, serde_json::to_string(&lock).unwrap()).unwrap();

        let mut calibration_value = Calibration {
            format: 1,
            status: "reviewed".into(),
            detector: detector("stale"),
            thresholds: Thresholds {
                review: 0.8,
                block: 0.9,
            },
            samples: vec![Sample {
                left: "left".into(),
                right: "right".into(),
                score: 0.95,
                label: "duplicate".into(),
            }],
        };
        fs::write(
            &calibration_path,
            serde_yaml::to_string(&calibration_value).unwrap(),
        )
        .unwrap();
        assert!(calibration(CalibrationCommand::Validate {
            calibration: calibration_path.clone(),
            model_lock: model_lock_path.clone(),
        })
        .unwrap_err()
        .contains("explicitly recalibrate"));

        calibration_value.detector = detector(&lock_digest);
        fs::write(
            &calibration_path,
            serde_yaml::to_string(&calibration_value).unwrap(),
        )
        .unwrap();
        let baseline_value = Baseline {
            format: 1,
            status: "reviewed".into(),
            detector: detector("stale"),
            calibration_digest: calibration_digest(&calibration_value).unwrap(),
            block_threshold: 0.9,
            findings: BTreeMap::new(),
        };
        fs::write(
            &baseline_path,
            serde_yaml::to_string(&baseline_value).unwrap(),
        )
        .unwrap();
        assert!(baseline(BaselineCommand::Validate {
            baseline: baseline_path.clone(),
            calibration: calibration_path.clone(),
            model_lock: model_lock_path.clone(),
        })
        .unwrap_err()
        .contains("explicitly rebaseline"));

        for path in [model_lock_path, calibration_path, baseline_path] {
            let _ = fs::remove_file(path);
        }
    }

    fn relative_ref(path: &str, kind: RefKind) -> RelativeRef {
        RelativeRef {
            path: path.into(),
            kind,
        }
    }

    fn detector(lock: &str) -> Detector {
        Detector {
            version: DETECTOR_VERSION.into(),
            model_lock_digest: lock.into(),
            chunker: CHUNKER_VERSION.into(),
            pooling: MODEL_POOLING.into(),
            normalization: MODEL_NORMALIZATION.into(),
        }
    }

    fn disposition(status: &str, tokens: usize) -> Disposition {
        Disposition {
            status: status.into(),
            reason: Some("reviewed".into()),
            issue: None,
            lane: "body".into(),
            graph_class: "disconnected".into(),
            duplicate_tokens_estimate: tokens,
            component_tokens_estimate: tokens,
        }
    }

    fn valid_lock() -> ModelLock {
        ModelLock {
            format: 1,
            model: "snowflake/snowflake-arctic-embed-s".into(),
            revision: MODEL_REVISION.into(),
            fastembed: "5.17.3".into(),
            dimensions: 384,
            execution_provider: PARITY_EXECUTION_PROVIDER.into(),
            threads: 1,
            batch_size: 32,
            passage_prefix: String::new(),
            pooling: MODEL_POOLING.into(),
            normalization: MODEL_NORMALIZATION.into(),
            artifacts: REQUIRED_ARTIFACTS
                .iter()
                .map(|path| Artifact {
                    path: (*path).into(),
                    sha256: "0".repeat(64),
                })
                .collect(),
        }
    }

    fn test_section(path: &str, headings: &[&str], span: Span, body: &str) -> Section {
        Section {
            path: path.into(),
            headings: headings.iter().map(|value| (*value).into()).collect(),
            span,
            body: body.into(),
            refs: vec![],
            pointer: false,
        }
    }

    fn test_finding(id: &str, kind: &str, score: Option<f32>, tokens: usize) -> Finding {
        let mut left = test_chunk(&format!("{id}-left.md"), &["Doc", "Left"], 1, "left");
        let mut right = test_chunk(&format!("{id}-right.md"), &["Doc", "Right"], 1, "right");
        left.tokens = tokens;
        right.tokens = tokens;
        Finding {
            id: id.into(),
            lane: "body".into(),
            detector: DETECTOR_VERSION.into(),
            kind: kind.into(),
            left,
            right,
            graph: GraphClass {
                directly_linked: false,
                directed_distance: None,
                undirected_distance: None,
                same_component: false,
                same_skill: false,
                disconnected: true,
            },
            score,
            duplicate_tokens_estimate: tokens,
        }
    }

    fn scored_report_finding(id: &str, kind: &str, cosine: Option<f32>) -> ReportFinding {
        let mut finding = test_finding(id, kind, cosine, 1);
        finding.left.original_excerpt = format!("{id} left");
        finding.right.original_excerpt = format!("{id} right");
        report_finding(&finding)
    }

    fn test_chunk(path: &str, headings: &[&str], part: usize, source_hash: &str) -> Chunk {
        Chunk {
            endpoint: Endpoint {
                path: path.into(),
                heading_path: headings.iter().map(|value| (*value).into()).collect(),
                part,
                source_hash: source_hash.into(),
                span: Span { start: 1, end: 2 },
            },
            payload: "payload".into(),
            evidence: "evidence".into(),
            original_excerpt: "original excerpt".into(),
            tokens: 1,
            original_span: Span { start: 1, end: 2 },
        }
    }

    fn temp_path(name: &str) -> PathBuf {
        std::env::temp_dir().join(format!(
            "skill-overlap-{}-{}-{name}",
            std::process::id(),
            TEMP_ID.fetch_add(1, Ordering::Relaxed)
        ))
    }

    fn temp_dir(name: &str) -> PathBuf {
        let path = temp_path(name);
        fs::create_dir_all(&path).unwrap();
        path
    }
}
