use clap::{Args, Parser, Subcommand, ValueEnum};
use regex::Regex;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    borrow::Cow,
    collections::{BTreeMap, BTreeSet, VecDeque},
    fs,
    path::{Path, PathBuf},
    sync::LazyLock,
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

static LINKS_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"\[[^\]]*\]\(([^)\s]+)\)").unwrap());
static TICKS_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"`([^`]+)`").unwrap());
static PROSE_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"^(?:\.\./)+[\w./-]+\.md(?:#[\w-]+)?$|^references/[\w./-]+\.md(?:#[\w-]+)?$")
        .unwrap()
});
static COMMENT_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"(?s)<!--.*?-->").unwrap());
static LIST_MARKER_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?m)^\s*(?:[-*+]|[0-9]+\.)\s+").unwrap());
static SHA_HEX_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"^[a-f0-9]{64}$").unwrap());

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
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
enum FindingKind {
    Exact,
    Semantic,
}
impl std::fmt::Display for FindingKind {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(match self {
            FindingKind::Exact => "exact",
            FindingKind::Semantic => "semantic",
        })
    }
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
enum DispositionStatus {
    Intentional,
    Debt,
    ReviewRequired,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
enum FindingDisposition {
    Intentional,
    Debt,
    Unaccepted,
    Advisory,
}
impl std::fmt::Display for FindingDisposition {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(match self {
            FindingDisposition::Intentional => "intentional",
            FindingDisposition::Debt => "debt",
            FindingDisposition::Unaccepted => "unaccepted",
            FindingDisposition::Advisory => "advisory",
        })
    }
}
impl From<DispositionStatus> for FindingDisposition {
    fn from(status: DispositionStatus) -> Self {
        match status {
            DispositionStatus::Intentional => FindingDisposition::Intentional,
            DispositionStatus::Debt => FindingDisposition::Debt,
            DispositionStatus::ReviewRequired => FindingDisposition::Unaccepted,
        }
    }
}
#[derive(Debug, Deserialize, Serialize, Clone)]
struct Disposition {
    status: DispositionStatus,
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
    refs: Vec<String>,
    pointer: bool,
}
#[derive(Debug, Clone)]
struct Document {
    path: String,
    refs: Vec<String>,
    sections: Vec<Section>,
}
#[derive(Debug, Clone, Serialize)]
struct Chunk {
    endpoint: Endpoint,
    payload: String,
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
    kind: FindingKind,
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
    kind: FindingKind,
    left: ReportEndpoint,
    right: ReportEndpoint,
    graph: GraphClass,
    cosine: Option<f32>,
    duplicate_tokens_estimate: usize,
    disposition: FindingDisposition,
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
    disposition: FindingDisposition,
    current_findings: usize,
    baseline_findings: usize,
    current_estimated_duplicate_tokens: usize,
    baseline_estimated_duplicate_tokens: usize,
}
#[derive(Debug, Serialize, Deserialize)]
struct Trends {
    groups: Vec<TrendGroup>,
}

fn main() -> std::process::ExitCode {
    let result = match Cli::parse().command {
        Command::Model {
            command: ModelCommand::Fetch(args),
        } => model_fetch(&args),
        Command::VerifyParity(args) => verify_parity(args),
        Command::Analyze(args) => analyze(args),
        Command::Calibration { command } => calibration(command),
        Command::Baseline { command } => baseline(command),
    };
    match result {
        Ok(()) => std::process::ExitCode::SUCCESS,
        Err(message) => {
            eprintln!("{message}");
            std::process::ExitCode::FAILURE
        }
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
fn execution_providers_for(
    provider: &str,
) -> Result<Vec<fastembed::ExecutionProviderDispatch>, String> {
    match provider {
        "onnxruntime-cpu" => Ok(Vec::new()),
        other => Err(format!("unsupported execution provider {other}")),
    }
}

#[cfg(feature = "model")]
fn load_embedder(model_dir: &Path, lock: &ModelLock) -> Result<fastembed::TextEmbedding, String> {
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
        InitOptionsUserDefined::new()
            .with_intra_threads(lock.threads as usize)
            .with_execution_providers(execution_providers_for(&lock.execution_provider)?),
    )
    .map_err(|error| format!("initialize verified local ONNX model: {error}"))
}

#[cfg(feature = "model")]
fn embed_payloads(
    model_dir: &Path,
    payloads: &[String],
    lock: &ModelLock,
) -> Result<Vec<Vec<f32>>, String> {
    let mut embedder = load_embedder(model_dir, lock)?;
    let prefixed = payloads
        .iter()
        .map(|payload| format!("{}{}", lock.passage_prefix, payload))
        .collect::<Vec<_>>();
    let vectors = embedder
        .embed(&prefixed, Some(lock.batch_size))
        .map_err(|error| format!("embed verified local chunks: {error}"))?;
    vectors
        .into_iter()
        .map(|mut vector| {
            if vector.len() != lock.dimensions {
                return Err(format!(
                    "embedder returned {} dimensions, expected {}",
                    vector.len(),
                    lock.dimensions
                ));
            }
            l2_normalize(&mut vector);
            Ok(vector)
        })
        .collect()
}

#[cfg(not(feature = "model"))]
fn embed_payloads(_: &Path, _: &[String], _: &ModelLock) -> Result<Vec<Vec<f32>>, String> {
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
        let actual = embed_payloads(&args.model.model_dir, &inputs, &lock)?;
        if actual.len() != cases.len() {
            return Err(format!(
                "parity failed: expected {} embeddings, got {}",
                cases.len(),
                actual.len()
            ));
        }
        for (case, actual) in cases.iter().zip(actual) {
            let expected = case["output"].as_array().unwrap();
            if expected.len() != actual.len() {
                return Err(format!(
                    "parity failed: expected {}-dim embedding, got {}",
                    expected.len(),
                    actual.len()
                ));
            }
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

fn line_offsets(text: &str) -> Vec<usize> {
    let mut offsets = vec![0usize];
    for (index, byte) in text.bytes().enumerate() {
        if byte == b'\n' {
            offsets.push(index + 1);
        }
    }
    offsets
}

fn byte_to_line(offsets: &[usize], byte: usize) -> usize {
    offsets.partition_point(|&start| start <= byte)
}

fn heading_level_number(level: pulldown_cmark::HeadingLevel) -> u8 {
    use pulldown_cmark::HeadingLevel;
    match level {
        HeadingLevel::H1 => 1,
        HeadingLevel::H2 => 2,
        HeadingLevel::H3 => 3,
        HeadingLevel::H4 => 4,
        HeadingLevel::H5 => 5,
        HeadingLevel::H6 => 6,
    }
}

fn heading_title(raw_lines: &[&str], start_line: usize, end_line: usize, level: u8) -> String {
    if end_line > start_line {
        // Setext heading: every line above the underline (=== or ---) is title text. A setext
        // heading's content is a whole paragraph, so it can span several physical lines; join
        // them rather than truncating to the first.
        raw_lines[start_line - 1..end_line - 1]
            .iter()
            .map(|line| line.trim())
            .collect::<Vec<_>>()
            .join(" ")
    } else {
        // ATX heading: re-slice the raw line so title text stays byte-identical to the
        // pre-pulldown-cmark implementation (do not use inline Event::Text/Event::Code,
        // which would strip markdown syntax like backticks or `**`).
        let raw = raw_lines[start_line - 1];
        let trimmed = raw.trim_start();
        let rest = trimmed.get(level as usize..).unwrap_or("");
        rest.trim_start_matches([' ', '\t']).trim().to_owned()
    }
}

// pulldown-cmark 0.13.4's `scan_closing_code_fence` only accepts ASCII space after the
// fence-char run, not tab:
// https://github.com/pulldown-cmark/pulldown-cmark/blob/v0.13.4/pulldown-cmark/src/scanners.rs#L528
// CommonMark 0.31.2 §4.5 says a closing fence "may be followed only by spaces or tabs,
// which are ignored" (the `cmark` reference impl accepts `[ \t]*`), so a trailing tab after
// a closing fence leaves pulldown-cmark's fence open, silently swallowing every later
// heading in the file. Rewrite the trailing-whitespace suffix of fence-shaped lines
// (tabs -> spaces only, never truncated) before handing the text to the parser; byte length
// is preserved so every byte offset -> line-number mapping stays identical to the original
// `text`, which is still what everything else (titles, body, refs) reads from.
fn normalize_fence_closer_tabs(text: &str) -> String {
    let mut out = String::with_capacity(text.len());
    for line in text.split_inclusive('\n') {
        let (content, ending) = match line.strip_suffix("\r\n") {
            Some(rest) => (rest, "\r\n"),
            None => match line.strip_suffix('\n') {
                Some(rest) => (rest, "\n"),
                None => (line, ""),
            },
        };
        out.push_str(&normalize_fence_shape_line(content));
        out.push_str(ending);
    }
    debug_assert_eq!(
        out.len(),
        text.len(),
        "normalize_fence_closer_tabs must preserve byte length"
    );
    out
}

fn normalize_fence_shape_line(line: &str) -> Cow<'_, str> {
    let indentation = line.bytes().take_while(|byte| *byte == b' ').count();
    if indentation > 3 {
        return Cow::Borrowed(line);
    }
    let trimmed = &line[indentation..];
    let marker = match trimmed.chars().next() {
        Some(character @ ('`' | '~')) => character,
        _ => return Cow::Borrowed(line),
    };
    let run_len = trimmed
        .chars()
        .take_while(|character| *character == marker)
        .count();
    if run_len < 3 {
        return Cow::Borrowed(line);
    }
    let suffix = &trimmed[run_len..];
    if suffix.is_empty()
        || !suffix.bytes().all(|byte| matches!(byte, b' ' | b'\t'))
        || !suffix.contains('\t')
    {
        return Cow::Borrowed(line);
    }
    let mut normalized = String::with_capacity(line.len());
    normalized.push_str(&line[..indentation + run_len]);
    for byte in suffix.bytes() {
        normalized.push(if byte == b'\t' { ' ' } else { byte as char });
    }
    Cow::Owned(normalized)
}

// A line that plausibly belongs to a YAML front-matter block: blank, a comment, a `key:`
// line (at any indent, since nested mappings and list-item bodies are legal frontmatter), or
// a `- ` list item (bare, or opening a nested mapping like `- text: Get started`). A run of
// 2+ `#` is a markdown ATX heading (`##`+), never a YAML comment, so it does not count -- this
// is what lets shape (1) below abort the scan instead of dot-filling real headings.
//
// Single `#` is deliberately tolerated as a YAML comment rather than aborting on a Markdown
// H1: a real H1 can only appear here if the block never was frontmatter (see the thematic-
// break shape-1 test, which the 2+-hash check above already catches -- Markdown documents
// virtually always follow a thematic-break `---` with content before a lone `#`, e.g. another
// heading or a paragraph, and the corpus scan backing this fix (23 files starting with `---`)
// contains no thematic-break opener that goes straight to a bare `#` line). Over-strictness
// here is the measured, currently-happening failure mode (a real frontmatter block aborts and
// reintroduces a phantom section); over-permissiveness only misfires on a document shape not
// observed in this repo. Given that asymmetry, tolerate.
fn is_yaml_line_shape(trimmed: &str) -> bool {
    let content = trimmed.trim_start();
    if content.is_empty() {
        return true;
    }
    let hashes = content
        .chars()
        .take_while(|character| *character == '#')
        .count();
    if hashes >= 2 {
        return false;
    }
    if hashes == 1 {
        return true;
    }
    if content == "-" {
        return true;
    }
    // Strip a list-item marker, if present, before checking mapping-key shape: both a bare
    // list item ("- Get started") and a list item opening a mapping ("- text: Get started")
    // are legal frontmatter.
    let rest = content.strip_prefix("- ").unwrap_or(content);
    match rest.split_once(':') {
        Some((key, _)) => !key.is_empty() && !key.contains(char::is_whitespace),
        None => rest.len() != content.len(),
    }
}

fn is_block_scalar_key(trimmed: &str) -> bool {
    trimmed
        .split_once(':')
        .map(|(_, value)| matches!(value.trim(), "|" | ">" | "|-" | "|+" | ">-" | ">+"))
        .unwrap_or(false)
}

// GitHub-style YAML front matter (`---\n...\n---\n`) at the very start of a file has no
// heading semantics in the legacy hand-rolled parser (it only recognizes `#`/`##`/`###`
// lines; front matter is inert text that predates any section). pulldown-cmark has no
// front-matter extension, so it reads the closing `---` as a setext H2 underline for the
// front-matter line above it, manufacturing a heading that never existed (confirmed via the
// Stage-A parity harness against every `.github/instructions/*.md` and `skills/*/SKILL.md`
// file, all of which open with `---`-delimited front matter). Neutralize the front-matter
// block (opening delimiter through closing delimiter, inclusive) to `.`-filled lines before
// parsing so it can never read as a heading or thematic break; length and line count stay
// identical so byte-to-line mapping is unaffected, and the ORIGINAL `text` is still what
// titles/body/refs are sliced from.
fn neutralize_front_matter(text: &str) -> String {
    let mut lines = text.split_inclusive('\n');
    let Some(first) = lines.next() else {
        return text.to_owned();
    };
    if first.trim_end_matches(['\r', '\n']) != "---" {
        return text.to_owned();
    }
    let mut consumed = first.len();
    let mut closing_len = None;
    let mut in_scalar = false;
    for line in lines {
        consumed += line.len();
        let indented = line.starts_with(' ') || line.starts_with('\t');
        let trimmed = line.trim_end_matches(['\r', '\n']);
        if in_scalar {
            if indented || trimmed.is_empty() {
                continue;
            }
            in_scalar = false;
        }
        if trimmed == "---" || trimmed == "..." {
            closing_len = Some(consumed);
            break;
        }
        if !is_yaml_line_shape(trimmed) {
            return text.to_owned();
        }
        if is_block_scalar_key(trimmed) {
            in_scalar = true;
        }
    }
    let Some(end) = closing_len else {
        return text.to_owned();
    };
    let mut out = String::with_capacity(text.len());
    for byte in text[..end].bytes() {
        out.push(if matches!(byte, b'\n' | b'\r') {
            byte as char
        } else {
            '.'
        });
    }
    out.push_str(&text[end..]);
    debug_assert_eq!(
        out.len(),
        text.len(),
        "neutralize_front_matter must preserve byte length"
    );
    out
}

// Both shims rewrite the parser's input only; the original `text` still feeds titles, body,
// and refs. They preserve byte length exactly, so a byte offset from an event parsed out of
// this string maps through `line_offsets(original)` to the same line it would have in the
// original. Every `Span` in the crate depends on that invariant, hence the assert.
fn parser_input(text: &str) -> String {
    let out = normalize_fence_closer_tabs(&neutralize_front_matter(text));
    debug_assert_eq!(
        out.len(),
        text.len(),
        "parser_input must preserve byte length"
    );
    out
}
fn parse_document(path: &Path, repo: &Path, counter: &TokenCounter) -> Result<Document, String> {
    use pulldown_cmark::{Event, Options, Parser, Tag};

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
    let finish = |current: &mut Option<(Vec<String>, usize, Vec<String>)>,
                  end: usize,
                  sections: &mut Vec<Section>|
     -> Result<(), String> {
        if let Some((headings, start, lines)) = current.take() {
            let body = lines.join("\n");
            let refs = extract_relative_refs(&body);
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

    let raw_lines: Vec<&str> = text.lines().collect();
    let total_lines = raw_lines.len();
    let offsets = line_offsets(&text);

    // Event scan: build a heading map keyed by the heading's start line, for H1-H3 only
    // (H4-H6 stay body content). Each entry carries (level, end_line) where end_line is
    // the last physical source line the heading occupies (== start_line for ATX,
    // start_line + 1 for setext).
    let mut heading_at: Vec<Option<(u8, usize)>> = vec![None; total_lines + 1];
    let parsed_input = parser_input(&text);
    let parser = Parser::new_ext(&parsed_input, Options::ENABLE_TABLES).into_offset_iter();
    for (event, range) in parser {
        if let Event::Start(Tag::Heading { level, .. }) = event {
            let level_num = heading_level_number(level);
            if !(1..=3).contains(&level_num) {
                continue;
            }
            let start_line = byte_to_line(&offsets, range.start);
            let end_byte = range.end.saturating_sub(1).max(range.start);
            let end_line = byte_to_line(&offsets, end_byte);
            heading_at[start_line] = Some((level_num, end_line));
        }
    }

    // Line loop: drives body accumulation and the finish/current dance, delegating only
    // heading detection (is-heading / level / fence-awareness) to pulldown-cmark above.
    let mut line_number = 1usize;
    while line_number <= total_lines {
        if let Some((level, end_line)) = heading_at[line_number] {
            let title = heading_title(&raw_lines, line_number, end_line, level);
            match level {
                1 => {
                    h1 = title;
                    h2.clear();
                }
                2 => {
                    finish(&mut current, line_number.saturating_sub(1), &mut sections)?;
                    h2 = title.clone();
                    current = Some((vec![h1.clone(), h2.clone()], end_line + 1, Vec::new()));
                }
                3 => {
                    finish(&mut current, line_number.saturating_sub(1), &mut sections)?;
                    let mut headings = vec![h1.clone()];
                    if !h2.is_empty() {
                        headings.push(h2.clone());
                    }
                    headings.push(title);
                    current = Some((headings, end_line + 1, Vec::new()));
                }
                _ => unreachable!("heading_at only stores levels 1-3"),
            }
            line_number = end_line + 1;
            continue;
        }
        if let Some((_, _, body)) = &mut current {
            body.push(raw_lines[line_number - 1].to_owned());
        }
        line_number += 1;
    }
    finish(&mut current, total_lines, &mut sections)?;
    Ok(Document {
        path: rel,
        refs: extract_relative_refs(&text),
        sections,
    })
}

fn extract_relative_refs(text: &str) -> Vec<String> {
    let links = &*LINKS_RE;
    let ticks = &*TICKS_RE;
    let prose = &*PROSE_RE;
    let mut refs = Vec::new();
    for capture in links.captures_iter(text) {
        let raw = &capture[1];
        if !["http://", "https://", "mailto:", "#"]
            .iter()
            .any(|prefix| raw.starts_with(prefix))
        {
            let path = raw.split('#').next().unwrap();
            if path.ends_with(".md") {
                refs.push(path.to_owned());
            }
        }
    }
    for capture in ticks.captures_iter(text) {
        let candidate = capture[1].split(" § ").next().unwrap();
        let probe = candidate.strip_suffix('\n').unwrap_or(candidate);
        if prose.is_match(probe) {
            refs.push(candidate.split('#').next().unwrap().to_owned());
        }
    }
    refs
}

fn pointer_only(body: &str, refs: &[String], counter: &TokenCounter) -> Result<bool, String> {
    let cleaned = COMMENT_RE.replace_all(body, "");
    let trimmed = cleaned
        .lines()
        .filter(|line| !matches!(line.trim(), "---" | "***" | "___"))
        .collect::<Vec<_>>()
        .join("\n");
    let normalized = normalize(&trimmed);
    let has_list = LIST_MARKER_RE.is_match(&trimmed);
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
    let target = regex::escape(&refs[0]);
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
            _ => unreachable!("no token counter variants configured"),
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

fn list_groups(lines: &[&str], body: &str) -> Vec<Option<usize>> {
    use pulldown_cmark::{Event, Options, Parser, Tag, TagEnd};
    let mut groups = vec![None; lines.len()];
    let offsets = line_offsets(body);
    let parsed_body = parser_input(body);
    let parser = Parser::new_ext(&parsed_body, Options::ENABLE_TABLES).into_offset_iter();
    let mut depth = 0i32;
    let mut item_start_byte = 0usize;
    let mut next_group = 0usize;
    for (event, range) in parser {
        match event {
            Event::Start(Tag::Item) => {
                if depth == 0 {
                    item_start_byte = range.start;
                }
                depth += 1;
            }
            Event::End(TagEnd::Item) => {
                depth -= 1;
                if depth == 0 {
                    next_group += 1;
                    let start_line = byte_to_line(&offsets, item_start_byte);
                    let end_byte = range.end.saturating_sub(1).max(item_start_byte);
                    let end_line = byte_to_line(&offsets, end_byte);
                    for line in start_line..=end_line {
                        if line >= 1 && line <= lines.len() {
                            groups[line - 1] = Some(next_group);
                        }
                    }
                }
            }
            _ => {}
        }
    }
    groups
}

fn table_contexts(lines: &[&str], section_start: usize, body: &str) -> Vec<Option<TableContext>> {
    use pulldown_cmark::{Event, Options, Parser, Tag, TagEnd};
    let mut contexts = vec![None; lines.len()];
    let offsets = line_offsets(body);
    let parsed_body = parser_input(body);
    let parser = Parser::new_ext(&parsed_body, Options::ENABLE_TABLES).into_offset_iter();
    let mut table_start_byte: Option<usize> = None;
    let mut header_line: Option<usize> = None;
    for (event, range) in parser {
        match event {
            Event::Start(Tag::Table(_)) => {
                table_start_byte = Some(range.start);
            }
            Event::Start(Tag::TableHead) => {
                header_line = Some(byte_to_line(&offsets, range.start));
            }
            Event::End(TagEnd::Table) => {
                if let (Some(start_byte), Some(head_line)) = (table_start_byte, header_line) {
                    let start_line = byte_to_line(&offsets, start_byte);
                    let end_byte = range.end.saturating_sub(1).max(start_byte);
                    let end_line = byte_to_line(&offsets, end_byte);
                    let header_text = lines.get(head_line - 1).copied().unwrap_or("").to_owned();
                    let context = TableContext {
                        header: header_text,
                        header_line: section_start + (head_line - 1),
                    };
                    for line in start_line..=end_line {
                        if line >= 1 && line <= lines.len() {
                            contexts[line - 1] = Some(context.clone());
                        }
                    }
                }
                table_start_byte = None;
                header_line = None;
            }
            _ => {}
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
    let groups = list_groups(&source_lines, &section.body);
    let tables = table_contexts(&source_lines, section.span.start, &section.body);
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
    let normalized = normalize(&section.body);
    Ok(Chunk {
        endpoint: Endpoint {
            path: section.path.clone(),
            heading_path: section.headings.clone(),
            part: 1,
            source_hash: digest(normalized.as_bytes()),
            span: section.span.clone(),
        },
        payload: section.body.clone(),
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
    forward: &Adjacency,
    undirected: &Adjacency,
    owner: &BTreeMap<String, usize>,
    graph_cache: &mut BTreeMap<(String, String), GraphClass>,
) -> Result<Vec<Finding>, String> {
    let sections = documents
        .iter()
        .flat_map(|document| &document.sections)
        .filter(|section| !normalize(&section.body).is_empty())
        .collect::<Vec<_>>();
    let mut buckets: BTreeMap<String, Vec<&Section>> = BTreeMap::new();
    for section in &sections {
        buckets
            .entry(normalize(&section.body))
            .or_default()
            .push(section);
    }
    let mut findings = Vec::new();
    for members in buckets.values().filter(|members| members.len() >= 2) {
        for (index, left_section) in members.iter().enumerate() {
            for right_section in members.iter().skip(index + 1) {
                let left = section_chunk(left_section, counter)?;
                let right = section_chunk(right_section, counter)?;
                findings.push(Finding {
                    id: identity(FindingKind::Exact, &left, &right, None),
                    lane: "body".into(),
                    detector: DETECTOR_VERSION.into(),
                    kind: FindingKind::Exact,
                    graph: memoized_graph_class(
                        graph_cache,
                        edges,
                        forward,
                        undirected,
                        owner,
                        &left,
                        &right,
                    ),
                    duplicate_tokens_estimate: left.tokens.min(right.tokens),
                    left,
                    right,
                    score: None,
                });
            }
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

type GraphEdges = BTreeMap<String, BTreeSet<String>>;

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
            let prefix_with_slash = format!("{prefix}/");
            for path in &paths {
                if *path == prefix || path.starts_with(&prefix_with_slash) {
                    owner.insert(path.clone(), index);
                }
            }
        }
    }
    for document in documents {
        let base = Path::new(&document.path).parent().unwrap_or(Path::new(""));
        let mut targets = BTreeSet::new();
        for reference in &document.refs {
            let joined = lexical_path(&base.join(reference));
            if paths.contains(&joined) {
                targets.insert(joined);
            }
        }
        edges.insert(document.path.clone(), targets);
    }
    (edges, owner)
}

type Adjacency = BTreeMap<String, BTreeSet<String>>;

fn forward_adjacency(edges: &GraphEdges) -> Adjacency {
    edges
        .iter()
        .map(|(from, targets)| (from.clone(), targets.clone()))
        .collect()
}

fn undirected_adjacency(edges: &GraphEdges) -> Adjacency {
    let mut result: Adjacency = BTreeMap::new();
    for (from, targets) in edges {
        for to in targets {
            result.entry(from.clone()).or_default().insert(to.clone());
            result.entry(to.clone()).or_default().insert(from.clone());
        }
    }
    result
}

fn distances(adjacency: &Adjacency, from: &str, to: &str) -> Option<usize> {
    let mut queue = VecDeque::from([(from.to_owned(), 0)]);
    let mut seen = BTreeSet::new();
    while let Some((node, depth)) = queue.pop_front() {
        if !seen.insert(node.clone()) {
            continue;
        }
        if node == to {
            return Some(depth);
        }
        if let Some(next) = adjacency.get(&node) {
            for next_node in next {
                queue.push_back((next_node.clone(), depth + 1));
            }
        }
    }
    None
}
fn graph_class(
    edges: &GraphEdges,
    forward: &Adjacency,
    undirected: &Adjacency,
    owner: &BTreeMap<String, usize>,
    a: &Chunk,
    b: &Chunk,
) -> GraphClass {
    let linked = |from: &str, to: &str| edges.get(from).is_some_and(|targets| targets.contains(to));
    let direct =
        linked(&a.endpoint.path, &b.endpoint.path) || linked(&b.endpoint.path, &a.endpoint.path);
    let directed = match (
        distances(forward, &a.endpoint.path, &b.endpoint.path),
        distances(forward, &b.endpoint.path, &a.endpoint.path),
    ) {
        (Some(a_to_b), Some(b_to_a)) => Some(a_to_b.min(b_to_a)),
        (Some(distance), None) | (None, Some(distance)) => Some(distance),
        (None, None) => None,
    };
    let undirected = distances(undirected, &a.endpoint.path, &b.endpoint.path);
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
fn memoized_graph_class(
    cache: &mut BTreeMap<(String, String), GraphClass>,
    edges: &GraphEdges,
    forward: &Adjacency,
    undirected: &Adjacency,
    owner: &BTreeMap<String, usize>,
    a: &Chunk,
    b: &Chunk,
) -> GraphClass {
    let key = if a.endpoint.path <= b.endpoint.path {
        (a.endpoint.path.clone(), b.endpoint.path.clone())
    } else {
        (b.endpoint.path.clone(), a.endpoint.path.clone())
    };
    if let Some(cached) = cache.get(&key) {
        return cached.clone();
    }
    let class = graph_class(edges, forward, undirected, owner, a, b);
    cache.insert(key, class.clone());
    class
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

fn identity(kind: FindingKind, a: &Chunk, b: &Chunk, lock_digest: Option<&str>) -> String {
    let (left, right) = if a.endpoint <= b.endpoint {
        (a, b)
    } else {
        (b, a)
    };
    let model_identity = if kind == FindingKind::Semantic {
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

fn report_finding_with_disposition(
    finding: &Finding,
    disposition: FindingDisposition,
) -> ReportFinding {
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
        disposition,
    }
}

#[cfg(test)]
fn report_finding(finding: &Finding) -> ReportFinding {
    report_finding_with_disposition(finding, FindingDisposition::Unaccepted)
}

const SCORE_STRATA: [(f32, f32); 5] = [(-1.0, 0.5), (0.5, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.0)];

fn score_stratum(score: f32) -> usize {
    let score = score.clamp(-1.0, 1.0);
    SCORE_STRATA
        .iter()
        .position(|(min, max)| score >= *min && (score < *max || (*max == 1.0 && score <= *max)))
        .unwrap_or_else(|| {
            debug_assert!(
                score.is_nan(),
                "score {score} should be clamped to the calibration strata"
            );
            0
        })
}

#[cfg(test)]
fn sample_endpoint(endpoint: &ReportEndpoint) -> String {
    format!(
        "{}#{}#part-{}#{}",
        endpoint.path,
        endpoint.heading_path.join(" > "),
        endpoint.part,
        endpoint.source_hash
    )
}

fn sample_endpoint_from_chunk(chunk: &Chunk) -> String {
    format!(
        "{}#{}#part-{}#{}",
        chunk.endpoint.path,
        chunk.endpoint.heading_path.join(" > "),
        chunk.endpoint.part,
        chunk.endpoint.source_hash
    )
}

/// Streams stratum counts + one representative sample per stratum directly from
/// chunk/vector pairs, avoiding materializing a `Finding`/`ReportFinding` per pair.
/// Calibrate mode's score floor is -1.0, so every eligible pair is otherwise kept.
fn calibrate_score_distribution(
    chunks: &[Chunk],
    vectors: &[Vec<f32>],
    floor: f32,
    lock_digest: &str,
) -> CalibrationData {
    let mut counts = vec![0usize; SCORE_STRATA.len()];
    let mut selected = BTreeMap::<usize, (String, Sample)>::new();
    for (left_index, left) in chunks.iter().enumerate() {
        for (right_index, right) in chunks.iter().enumerate().skip(left_index + 1) {
            if !semantic_pair_eligible(left, right) {
                continue;
            }
            let score = cosine(&vectors[left_index], &vectors[right_index]);
            if score < floor {
                continue;
            }
            let stratum = score_stratum(score);
            counts[stratum] += 1;
            let id = identity(FindingKind::Semantic, left, right, Some(lock_digest));
            let sample = || Sample {
                left: sample_endpoint_from_chunk(left),
                right: sample_endpoint_from_chunk(right),
                score,
                label: "review-required".into(),
            };
            selected
                .entry(stratum)
                .and_modify(|(current_id, current_sample)| {
                    if id < *current_id {
                        *current_id = id.clone();
                        *current_sample = sample();
                    }
                })
                .or_insert_with(|| (id.clone(), sample()));
        }
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
        samples: selected.into_values().map(|(_, sample)| sample).collect(),
    }
}

#[cfg(test)]
fn calibration_data(findings: &[ReportFinding]) -> CalibrationData {
    let semantic = findings
        .iter()
        .filter(|finding| finding.kind == FindingKind::Semantic && finding.cosine.is_some())
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

fn finding_disposition(
    finding: &Finding,
    baseline: Option<&Baseline>,
    block: f32,
) -> FindingDisposition {
    let blocking =
        finding.kind == FindingKind::Exact || finding.score.is_some_and(|score| score >= block);
    if !blocking {
        return FindingDisposition::Advisory;
    }
    baseline
        .and_then(|baseline| baseline.findings.get(&finding.id))
        .map(|disposition| disposition.status.into())
        .unwrap_or(FindingDisposition::Unaccepted)
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

fn trends(classified: &[(Finding, FindingDisposition)], baseline: Option<&Baseline>) -> Trends {
    type Key = (String, String, FindingDisposition);
    let current_component_tokens = duplicate_components(
        classified
            .iter()
            .filter(|(_, disposition)| *disposition != FindingDisposition::Advisory)
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
            *disposition,
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
                    disposition.status.into(),
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

fn validate_analysis_mode(
    mode: Mode,
    has_calibration: bool,
    has_baseline: bool,
) -> Result<(), String> {
    if matches!(mode, Mode::Calibrate) && has_calibration {
        Err("calibrate mode does not accept --calibration".into())
    } else if !matches!(mode, Mode::Check) && has_baseline {
        Err("--baseline is only accepted in check mode".into())
    } else {
        Ok(())
    }
}

fn analyze(args: AnalyzeArgs) -> Result<(), String> {
    validate_analysis_mode(
        args.mode,
        args.calibration.is_some(),
        args.baseline.is_some(),
    )?;
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
    let forward_edges = forward_adjacency(&edges);
    let undirected_edges = undirected_adjacency(&edges);
    let mut graph_cache: BTreeMap<(String, String), GraphClass> = BTreeMap::new();
    let mut findings = exact_findings(
        &docs,
        &counter,
        &edges,
        &forward_edges,
        &undirected_edges,
        &owner,
        &mut graph_cache,
    )?;
    let chunks = chunks(&docs, &counter)?;
    let vectors = embed_payloads(
        &args.model_dir,
        &chunks
            .iter()
            .map(|chunk| chunk.payload.clone())
            .collect::<Vec<_>>(),
        &lock,
    )?;
    let report_calibration = if matches!(args.mode, Mode::Calibrate) {
        Some(calibrate_score_distribution(
            &chunks,
            &vectors,
            floor,
            &lock_digest,
        ))
    } else {
        for (left_index, left) in chunks.iter().enumerate() {
            for (right_index, right) in chunks.iter().enumerate().skip(left_index + 1) {
                if !semantic_pair_eligible(left, right) {
                    continue;
                }
                let score = cosine(&vectors[left_index], &vectors[right_index]);
                if score >= floor {
                    findings.push(Finding {
                        id: identity(FindingKind::Semantic, left, right, Some(&lock_digest)),
                        lane: "body".into(),
                        detector: DETECTOR_VERSION.into(),
                        kind: FindingKind::Semantic,
                        left: left.clone(),
                        right: right.clone(),
                        graph: memoized_graph_class(
                            &mut graph_cache,
                            &edges,
                            &forward_edges,
                            &undirected_edges,
                            &owner,
                            left,
                            right,
                        ),
                        score: Some(score),
                        duplicate_tokens_estimate: left.tokens.min(right.tokens),
                    });
                }
            }
        }
        None
    };
    let classified = findings
        .into_iter()
        .map(|finding| {
            let disposition = finding_disposition(&finding, baseline.as_ref(), block);
            (finding, disposition)
        })
        .collect::<Vec<_>>();
    let report_findings = classified
        .iter()
        .filter(|(_, disposition)| *disposition != FindingDisposition::Intentional)
        .map(|(finding, disposition)| report_finding_with_disposition(finding, *disposition))
        .collect::<Vec<_>>();
    let report_components = duplicate_components(
        classified
            .iter()
            .filter(|(_, disposition)| {
                *disposition != FindingDisposition::Intentional
                    && *disposition != FindingDisposition::Advisory
            })
            .map(|(finding, _)| finding),
    );
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
        frontmatter: frontmatter_advisories(&roots, &args.repo, floor)?,
        calibration: report_calibration,
        reviewed_calibration: reviewed,
    };
    if let Some(parent) = args.json_out.parent() {
        fs::create_dir_all(parent).map_err(ioerr)?;
    }
    if let Some(parent) = args.markdown_out.parent() {
        fs::create_dir_all(parent).map_err(ioerr)?;
    }
    fs::write(
        &args.json_out,
        serde_json::to_string_pretty(&report).map_err(|error| error.to_string())?,
    )
    .map_err(ioerr)?;
    fs::write(&args.markdown_out, markdown(&report)).map_err(ioerr)?;
    let blocked = classified
        .iter()
        .filter(|(_, disposition)| *disposition == FindingDisposition::Unaccepted)
        .filter(|(finding, _)| {
            finding.kind == FindingKind::Exact || finding.score.is_some_and(|score| score >= block)
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

const FRONTMATTER_ADVISORY_CAP: usize = 20;
fn frontmatter_advisories(
    roots: &[PathBuf],
    repo: &Path,
    floor: f32,
) -> Result<Vec<Advisory>, String> {
    let mut values = Vec::new();
    for root in roots {
        let file = root.join("SKILL.md");
        let text =
            fs::read_to_string(&file).map_err(|error| format!("{}: {error}", file.display()))?;
        let rel = file
            .strip_prefix(repo)
            .unwrap_or(&file)
            .to_string_lossy()
            .replace('\\', "/");
        if let Some(frontmatter) = text.strip_prefix("---\n").and_then(|body| {
            body.split_once("\n---\n")
                .map(|(frontmatter, _)| frontmatter)
        }) {
            let yaml: serde_yaml::Value = serde_yaml::from_str(frontmatter)
                .map_err(|error| format!("{}: {error}", file.display()))?;
            for field in ["name", "description"] {
                if let Some(value) = yaml.get(field).and_then(|value| value.as_str()) {
                    values.push(FrontmatterValue {
                        path: rel.clone(),
                        field: field.to_owned(),
                        value: value.to_owned(),
                    });
                }
            }
        }
    }
    let mut results = Vec::new();
    for (left_index, left_value) in values.iter().enumerate() {
        for right_value in values.iter().skip(left_index + 1) {
            if left_value.field == right_value.field {
                let score = lexical_strings(&left_value.value, &right_value.value);
                if score >= floor {
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
    results.sort_by(|a, b| b.score.total_cmp(&a.score));
    results.truncate(FRONTMATTER_ADVISORY_CAP);
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
    let digest_is_valid = SHA_HEX_RE.is_match(&value.calibration_digest);
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
        if !matches!(
            disposition.status,
            DispositionStatus::Intentional | DispositionStatus::Debt
        ) || disposition
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
                    finding.kind == FindingKind::Exact
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
                            status: DispositionStatus::ReviewRequired,
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
    #[cfg(feature = "model")]
    fn execution_providers_for_rejects_unknown_provider() {
        let error = execution_providers_for("bogus").unwrap_err();
        assert_eq!(error, "unsupported execution provider bogus");
    }

    #[test]
    #[cfg(feature = "model")]
    fn execution_providers_for_accepts_locked_cpu_provider() {
        let providers = execution_providers_for("onnxruntime-cpu").unwrap();
        assert!(providers.is_empty());
    }
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
        assert_eq!(
            cases.as_array().unwrap().len(),
            3,
            "expected 3 fixture cases"
        );
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
    fn frontmatter_advisory_below_floor_is_suppressed() {
        let root_a = temp_dir("frontmatter-floor-a");
        fs::write(
            root_a.join("SKILL.md"),
            "---\nname: alpha\ndescription: the quick fox jumps\n---\nBody\n",
        )
        .unwrap();
        let root_b = temp_dir("frontmatter-floor-b");
        fs::write(
            root_b.join("SKILL.md"),
            "---\nname: beta\ndescription: the slow turtle walks\n---\nBody\n",
        )
        .unwrap();

        let results = frontmatter_advisories(
            &[root_a.clone(), root_b.clone()],
            &std::env::temp_dir(),
            0.3,
        )
        .unwrap();
        assert!(
            results.is_empty(),
            "near-zero-score pair should be suppressed by the floor: {results:?}"
        );

        let _ = fs::remove_dir_all(root_a);
        let _ = fs::remove_dir_all(root_b);
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
                format!("# Doc\n## One\n```md\n{invalid_closer}\n## fake\n``` \t\n## Two\nbody\n"),
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
        assert_eq!(
            pieces.iter().map(String::len).collect::<Vec<_>>(),
            vec![10, 10, 5]
        );
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
    fn graph_dedupes_target_reachable_by_link_and_backtick_reference() {
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
            BTreeSet::from(["references/b.md".to_owned()])
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
        left.refs = extract_relative_refs(&left.body);
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
            &BTreeMap::new(),
            &BTreeMap::new(),
            &mut BTreeMap::new(),
        )
        .unwrap();
        assert_eq!(findings.len(), 1);
        assert_eq!(findings[0].kind, FindingKind::Exact);
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
                refs: vec!["../b/SKILL.md".to_owned()],
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
        let forward_edges = forward_adjacency(&edges);
        let undirected_edges = undirected_adjacency(&edges);
        let left = test_chunk("skills/a/SKILL.md", &["A", "Body"], 1, "a");
        let right = test_chunk("skills/b/SKILL.md", &["B", "Body"], 1, "b");
        assert!(
            graph_class(
                &edges,
                &forward_edges,
                &undirected_edges,
                &owner,
                &left,
                &right
            )
            .directly_linked
        );
    }

    #[test]
    fn graph_root_does_not_claim_sibling_directory_with_shared_prefix() {
        let documents = vec![
            Document {
                path: "skills/gh/SKILL.md".into(),
                refs: vec![],
                sections: vec![],
            },
            Document {
                path: "skills/gh-bootstrap/SKILL.md".into(),
                refs: vec![],
                sections: vec![],
            },
        ];
        let roots = vec![
            PathBuf::from("skills/gh"),
            PathBuf::from("skills/gh-bootstrap"),
        ];
        let (_, owner) = graph(&documents, &roots, Path::new(""));
        assert_eq!(owner.get("skills/gh/SKILL.md"), Some(&0));
        assert_eq!(owner.get("skills/gh-bootstrap/SKILL.md"), Some(&1));
    }

    #[test]
    fn identity_uses_complete_unordered_endpoint_identity() {
        let base = test_chunk("skills/a/SKILL.md", &["Doc", "One"], 1, "same");
        let other = test_chunk("skills/b/SKILL.md", &["Doc", "Other"], 1, "other");
        let changed_heading = test_chunk("skills/a/SKILL.md", &["Doc", "Two"], 1, "same");
        let changed_part = test_chunk("skills/a/SKILL.md", &["Doc", "One"], 2, "same");
        let id = identity(FindingKind::Semantic, &base, &other, Some("lock"));
        assert_ne!(
            id,
            identity(
                FindingKind::Semantic,
                &changed_heading,
                &other,
                Some("lock")
            )
        );
        assert_ne!(
            id,
            identity(FindingKind::Semantic, &changed_part, &other, Some("lock"))
        );
        assert_eq!(
            id,
            identity(FindingKind::Semantic, &other, &base, Some("lock"))
        );
    }

    #[test]
    fn exact_identity_ignores_model_lock_while_semantic_identity_tracks_it() {
        let left = test_chunk("skills/a/SKILL.md", &["Doc", "One"], 1, "left");
        let right = test_chunk("skills/b/SKILL.md", &["Doc", "Two"], 1, "right");

        assert_eq!(
            identity(FindingKind::Exact, &left, &right, Some("first-lock")),
            identity(FindingKind::Exact, &left, &right, Some("second-lock"))
        );
        assert_ne!(
            identity(FindingKind::Semantic, &left, &right, Some("first-lock")),
            identity(FindingKind::Semantic, &left, &right, Some("second-lock"))
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
        let intentional = test_finding("intentional-id", FindingKind::Exact, None, 7);
        let debt = test_finding("debt-id", FindingKind::Semantic, Some(0.95), 11);
        let baseline = Baseline {
            format: 1,
            status: "reviewed".into(),
            detector: detector("lock"),
            calibration_digest: "a".repeat(64),
            block_threshold: 0.9,
            findings: BTreeMap::from([
                (
                    intentional.id.clone(),
                    disposition(DispositionStatus::Intentional, 7),
                ),
                (debt.id.clone(), disposition(DispositionStatus::Debt, 11)),
            ]),
        };
        assert_eq!(
            finding_disposition(&intentional, Some(&baseline), 0.9),
            FindingDisposition::Intentional
        );
        assert_eq!(
            finding_disposition(&debt, Some(&baseline), 0.9),
            FindingDisposition::Debt
        );
        let classified = vec![
            (intentional, FindingDisposition::Intentional),
            (debt, FindingDisposition::Debt),
        ];
        let trends = trends(&classified, Some(&baseline));
        let intentional = trends
            .groups
            .iter()
            .find(|group| group.disposition == FindingDisposition::Intentional)
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
            let mut finding =
                test_finding(id, FindingKind::Exact, None, left.tokens.min(right.tokens));
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
            .map(|finding| (finding, FindingDisposition::Unaccepted))
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
        let mut first = test_finding("first", FindingKind::Exact, None, 10);
        first.left = left;
        first.right = middle.clone();
        first.graph.directly_linked = true;
        let mut second = test_finding("second", FindingKind::Exact, None, 20);
        second.left = middle;
        second.right = right;
        let classified = vec![
            (first, FindingDisposition::Debt),
            (second, FindingDisposition::Unaccepted),
        ];
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
                .find(|group| group.disposition == FindingDisposition::Debt)
                .unwrap()
                .current_estimated_duplicate_tokens,
            30
        );
    }

    #[test]
    fn report_serialization_and_markdown_preserve_finding_evidence() {
        let mut finding = test_finding("stable-id", FindingKind::Semantic, Some(0.875), 7);
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
        let finding = report_finding_with_disposition(&finding, FindingDisposition::Debt);
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
                    disposition: FindingDisposition::Debt,
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
            scored_report_finding("z-low", FindingKind::Semantic, Some(0.2)),
            scored_report_finding("z-mid", FindingKind::Semantic, Some(0.55)),
            scored_report_finding("a-mid", FindingKind::Semantic, Some(0.56)),
            scored_report_finding("z-related", FindingKind::Semantic, Some(0.75)),
            scored_report_finding("z-review", FindingKind::Semantic, Some(0.85)),
            scored_report_finding("z-block", FindingKind::Semantic, Some(0.95)),
            scored_report_finding("exact-is-excluded", FindingKind::Exact, None),
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
        assert!(validate_analysis_mode(Mode::Calibrate, false, false).is_ok());
        assert!(validate_analysis_mode(Mode::Report, true, false).is_ok());
        assert!(validate_analysis_mode(Mode::Calibrate, true, false)
            .unwrap_err()
            .contains("does not accept --calibration"));
    }

    #[test]
    fn report_mode_rejects_baseline_outside_check_mode() {
        assert!(validate_analysis_mode(Mode::Check, false, true).is_ok());
        assert!(validate_analysis_mode(Mode::Report, false, true)
            .unwrap_err()
            .contains("--baseline is only accepted in check mode"));
        assert!(validate_analysis_mode(Mode::Calibrate, false, true)
            .unwrap_err()
            .contains("--baseline is only accepted in check mode"));
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
                scored_report_finding("below", FindingKind::Semantic, Some(0.92)),
                scored_report_finding("above", FindingKind::Semantic, Some(0.96)),
                scored_report_finding("exact", FindingKind::Exact, None),
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

    // A misspelled disposition must fail loudly at deserialize rather than reaching the
    // block/allow decision, where it would read as "not intentional" and silently pass a
    // real duplicate through a green CI run.
    #[test]
    fn misspelled_disposition_status_is_rejected_at_deserialize() {
        let disposition = |status: &str| {
            format!(
                "status: {status}\nreason: accepted\nlane: body\ngraph_class: linked\nduplicate_tokens_estimate: 10\n"
            )
        };

        for accepted in ["intentional", "debt", "review-required"] {
            serde_yaml::from_str::<Disposition>(&disposition(accepted))
                .unwrap_or_else(|error| panic!("{accepted} must deserialize: {error}"));
        }

        for typo in ["intentionl", "Intentional", "dept", "unaccepted", ""] {
            assert!(
                serde_yaml::from_str::<Disposition>(&disposition(typo)).is_err(),
                "{typo:?} must be rejected, not treated as a non-blocking disposition"
            );
        }
    }

    // `identity()` interpolates the kind into the digest text, so these strings are part of
    // the on-disk fingerprint: changing them silently rebaselines every finding.
    #[test]
    fn finding_kind_display_is_stable_wire_text() {
        assert_eq!(FindingKind::Exact.to_string(), "exact");
        assert_eq!(FindingKind::Semantic.to_string(), "semantic");
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

    fn detector(lock: &str) -> Detector {
        Detector {
            version: DETECTOR_VERSION.into(),
            model_lock_digest: lock.into(),
            chunker: CHUNKER_VERSION.into(),
            pooling: MODEL_POOLING.into(),
            normalization: MODEL_NORMALIZATION.into(),
        }
    }

    fn disposition(status: DispositionStatus, tokens: usize) -> Disposition {
        Disposition {
            status,
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

    fn test_finding(id: &str, kind: FindingKind, score: Option<f32>, tokens: usize) -> Finding {
        let mut left = test_chunk(&format!("{id}-left.md"), &["Doc", "Left"], 1, "left");
        let mut right = test_chunk(&format!("{id}-right.md"), &["Doc", "Right"], 1, "right");
        left.tokens = tokens;
        right.tokens = tokens;
        Finding {
            id: id.into(),
            lane: "body".into(),
            detector: DETECTOR_VERSION.into(),
            kind,
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

    fn scored_report_finding(id: &str, kind: FindingKind, cosine: Option<f32>) -> ReportFinding {
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

    #[test]
    fn committed_calibration_seed_deserializes() {
        let yaml = include_str!("../../../.github/skill-overlap-calibration.yml");
        let calibration: Calibration = serde_yaml::from_str(yaml).unwrap();
        assert_eq!(calibration.detector.chunker, CHUNKER_VERSION);
        assert_eq!(calibration.detector.pooling, MODEL_POOLING);
        assert_eq!(calibration.detector.normalization, MODEL_NORMALIZATION);
    }

    #[test]
    fn committed_baseline_seed_deserializes() {
        let yaml = include_str!("../../../.github/skill-overlap-baseline.yml");
        let baseline: Baseline = serde_yaml::from_str(yaml).unwrap();
        assert_eq!(baseline.detector.chunker, CHUNKER_VERSION);
        assert_eq!(baseline.detector.pooling, MODEL_POOLING);
        assert_eq!(baseline.detector.normalization, MODEL_NORMALIZATION);
        assert!(baseline.findings.is_empty());
    }

    #[test]
    fn setext_h2_opens_a_section_and_setext_h1_only_sets_the_parent_heading() {
        // Setext (=== / ---) headings never split sections in the pre-pulldown parser, which
        // only recognized `#`/`##`/`###` lines; pulldown-cmark understands setext natively.
        // The blank lines are required: without them the paragraph above `---` would absorb
        // the preceding line into a single multi-line setext heading.
        let root = temp_path("setext.md");
        fs::write(&root, "# Doc\nOne\n===\n\nfirst\n\nTwo\n---\n\nsecond\n").unwrap();
        let doc = parse_document(&root, root.parent().unwrap(), &TokenCounter::Test).unwrap();
        // Setext H1 `One` replaces the `# Doc` parent context without opening a section of
        // its own, exactly as an ATX H1 does; only the setext H2 `Two` opens one.
        assert_eq!(doc.sections.len(), 1);
        assert_eq!(doc.sections[0].headings, vec!["One", "Two"]);
        assert_eq!(doc.sections[0].span, Span { start: 9, end: 10 });
        assert_eq!(doc.sections[0].body, "\nsecond");
        let _ = fs::remove_file(root);
    }

    #[test]
    fn multi_line_setext_heading_title_joins_every_line_above_the_underline() {
        // A setext heading's content is a paragraph, so it may span several physical lines.
        // Truncating to the first line would silently drop half the heading's identity, and
        // headings feed `Endpoint.heading_path` used for finding identity.
        let root = temp_path("setext-multiline.md");
        fs::write(&root, "# Doc\nfirst\nTwo\n---\nbody\n").unwrap();
        let doc = parse_document(&root, root.parent().unwrap(), &TokenCounter::Test).unwrap();
        assert_eq!(doc.sections.len(), 1);
        assert_eq!(doc.sections[0].headings, vec!["Doc", "first Two"]);
        assert_eq!(doc.sections[0].body, "body");
        let _ = fs::remove_file(root);
    }

    #[test]
    fn indented_h1_up_to_three_spaces_is_still_a_heading_finding_28() {
        // finding 28: a 1-3-space-indented H1 is CommonMark-legal and must still open a
        // section, matching the tolerance the legacy code already gave H2/H3.
        let root = temp_path("indent-h1.md");
        fs::write(&root, "   # Title\n## Sub\nbody\n").unwrap();
        let doc = parse_document(&root, root.parent().unwrap(), &TokenCounter::Test).unwrap();
        assert_eq!(
            doc.sections[0].headings,
            vec!["Title".to_string(), "Sub".to_string()]
        );
        let _ = fs::remove_file(root);
    }

    #[test]
    fn four_space_indented_hash_is_code_not_a_heading() {
        // CommonMark treats 4+ leading spaces as an indented code block, not a heading — the
        // legacy hand-rolled scanner had no indent limit and would have wrongly split here.
        let root = temp_path("indent-code.md");
        fs::write(&root, "    # Not a heading\n## Sub\nbody\n").unwrap();
        let doc = parse_document(&root, root.parent().unwrap(), &TokenCounter::Test).unwrap();
        assert_eq!(
            doc.sections[0].headings,
            vec![String::new(), "Sub".to_string()]
        );
        let _ = fs::remove_file(root);
    }

    #[test]
    fn headings_in_backtick_and_tilde_fences_require_matching_run_length() {
        // A closing fence must use the same character and be at least as long as the opener
        // (CommonMark run-length matching); a shorter run of the same char, or an info-string
        // line, must not close the fence and must not let interior '#' lines split sections.
        let root = temp_path("fence-runlen.md");
        fs::write(
            &root,
            "# Doc\n## One\n````rust\n## fake\n```\n#### still fenced\n````\n~~~~\n## fake2\n~~~\n~~~~\n## Two\nbody\n",
        )
        .unwrap();
        let doc = parse_document(&root, root.parent().unwrap(), &TokenCounter::Test).unwrap();
        assert_eq!(
            doc.sections
                .iter()
                .map(|section| section.headings.last().unwrap().as_str())
                .collect::<Vec<_>>(),
            vec!["One", "Two"]
        );
        let _ = fs::remove_file(root);
    }

    #[test]
    fn closing_fence_with_trailing_tab_closes() {
        // Pins the normalize_fence_closer_tabs shim directly: without it, pulldown-cmark
        // 0.13.4 leaves a tab-suffixed closing fence open, swallowing "## Two" into the
        // fenced block and merging it into section "One".
        let root = temp_path("fence-tab.md");
        fs::write(&root, "# Doc\n## One\n```\nfenced\n```\t\n## Two\nbody\n").unwrap();
        let doc = parse_document(&root, root.parent().unwrap(), &TokenCounter::Test).unwrap();
        assert_eq!(
            doc.sections
                .iter()
                .map(|section| section.headings.last().unwrap().as_str())
                .collect::<Vec<_>>(),
            vec!["One", "Two"]
        );
        let _ = fs::remove_file(root);
    }

    #[test]
    fn heading_titles_keep_inline_markdown_syntax_byte_identical() {
        // Titles are re-sliced from the raw source line, not built from pulldown-cmark's
        // inline Event::Text/Event::Code, so backticks and ** survive verbatim.
        let root = temp_path("inline-title.md");
        fs::write(&root, "# Doc\n## `just check` vs **just ci**\nbody\n").unwrap();
        let doc = parse_document(&root, root.parent().unwrap(), &TokenCounter::Test).unwrap();
        assert_eq!(
            doc.sections[0].headings.last().unwrap(),
            "`just check` vs **just ci**"
        );
        let _ = fs::remove_file(root);
    }

    #[test]
    fn h4_h5_h6_headings_stay_body_content() {
        let root = temp_path("h4-h6.md");
        fs::write(
            &root,
            "# Doc\n## One\n#### Four\nbody\n##### Five\n###### Six\n",
        )
        .unwrap();
        let doc = parse_document(&root, root.parent().unwrap(), &TokenCounter::Test).unwrap();
        assert_eq!(doc.sections.len(), 1);
        assert_eq!(
            doc.sections[0].body,
            "#### Four\nbody\n##### Five\n###### Six"
        );
        let _ = fs::remove_file(root);
    }

    #[test]
    fn nested_sublists_stay_in_one_list_group() {
        // list_groups groups by outermost Tag::Item, not outermost Tag::List: a top-level
        // item's nested sublist shares that item's group (child a/child b stay with parent
        // one), but sibling top-level items each get their own group so valid_cut can still
        // prefer the boundary between them (see boundary_rank's list-group-transition rank 6).
        let body = "- parent one\n  - child a\n  - child b\n- parent two\n";
        let lines: Vec<&str> = body.lines().collect();
        let groups = list_groups(&lines, body);
        assert_eq!(groups, vec![Some(1), Some(1), Some(1), Some(2)]);
    }

    #[test]
    fn gfm_tables_recognize_single_dash_and_triple_dash_header_delimiters() {
        // pulldown-cmark's GFM table extension accepts any run of one or more `-` (optionally
        // with `:` alignment markers) as the header-delimiter row; the legacy hand-rolled regex
        // required exactly `---`. Cover both forms so the newly-recognized single-dash case and
        // the legacy triple-dash case stay covered together.
        let single_dash = "| A | B |\n| - | - |\n| 1 | 2 |\n";
        let lines: Vec<&str> = single_dash.lines().collect();
        let contexts = table_contexts(&lines, 10, single_dash);
        assert!(contexts.iter().all(|context| context.is_some()));
        assert_eq!(contexts[0].as_ref().unwrap().header, "| A | B |");
        assert_eq!(contexts[0].as_ref().unwrap().header_line, 10);

        let triple_dash = "| A | B |\n| --- | --- |\n| 1 | 2 |\n";
        let lines: Vec<&str> = triple_dash.lines().collect();
        let contexts = table_contexts(&lines, 20, triple_dash);
        assert!(contexts.iter().all(|context| context.is_some()));
        assert_eq!(contexts[0].as_ref().unwrap().header, "| A | B |");
        assert_eq!(contexts[0].as_ref().unwrap().header_line, 20);
    }

    #[test]
    fn parser_input_shim_reaches_list_and_table_detection() {
        // Fix 1 pin: only parse_document routed the tab-closed-fence shim through
        // parser_input originally; list_groups and table_contexts parsed the raw section body
        // directly. A trailing-tab closing fence leaves pulldown-cmark's fence open for THEM
        // specifically, silently absorbing the list and table that follow. All three call
        // sites now route through parser_input.
        let body =
            "```\nfenced\n```\t\n- item one\n- item two\n\n| A | B |\n| - | - |\n| 1 | 2 |\n";
        let lines: Vec<&str> = body.lines().collect();

        let groups = list_groups(&lines, body);
        assert_eq!(
            groups[3],
            Some(1),
            "list item one must be detected past the tab-closed fence"
        );
        assert_eq!(
            groups[4],
            Some(2),
            "list item two must be detected past the tab-closed fence"
        );

        let contexts = table_contexts(&lines, 10, body);
        assert!(
            contexts[6].is_some() && contexts[7].is_some() && contexts[8].is_some(),
            "the GFM table past the tab-closed fence must be detected"
        );
        assert_eq!(contexts[6].as_ref().unwrap().header, "| A | B |");
    }

    #[test]
    fn sibling_top_level_list_items_cut_on_item_boundaries() {
        // list_groups now groups by outermost Tag::Item (sibling top-level items each get
        // their own group), so the boundary between two sibling items is a valid_cut and
        // ranks 6 in boundary_rank -- second only to an H4 heading. Chunk boundaries feed the
        // duplicate-detection ratchet directly: a chunk that opens cleanly at "- parent1"
        // carries more standalone context for embedding/matching than one that opens mid-item,
        // so cutting on the item boundary (rather than splitting parent1's children) is a real
        // chunk-quality improvement, not just cosmetic.
        let mut lines = Vec::new();
        for parent in 0..3 {
            lines.push(format!("- parent{parent}"));
            lines.extend((0..200).map(|child| format!("  child{parent}-{child}")));
        }
        let total = lines.len();
        let section = test_section(
            "x.md",
            &["Doc"],
            Span {
                start: 10,
                end: 10 + total - 1,
            },
            &lines.join("\n"),
        );

        let pieces = split_section(&section, 2, &TokenCounter::Test).unwrap();

        assert_eq!(pieces.len(), 3);
        assert_eq!(
            pieces[0].span,
            Span {
                start: 10,
                end: 210
            }
        );
        assert_eq!(
            pieces[1].span,
            Span {
                start: 211,
                end: 411
            }
        );
        assert_eq!(
            pieces[2].span,
            Span {
                start: 412,
                end: 612
            }
        );
        assert!(
            pieces[0].body.starts_with("- parent0") && pieces[0].body.ends_with("child0-199"),
            "piece 0 must be exactly parent0's item boundary, not a mid-item split: {:?}..{:?}",
            pieces[0].body.lines().next(),
            pieces[0].body.lines().last()
        );
        assert!(
            pieces[1].body.starts_with("- parent1") && pieces[1].body.ends_with("child1-199"),
            "piece 1 must start at the parent1 item boundary, not mid-item: {:?}..{:?}",
            pieces[1].body.lines().next(),
            pieces[1].body.lines().last()
        );
        assert!(
            pieces[2].body.starts_with("- parent2") && pieces[2].body.ends_with("child2-199"),
            "piece 2 must start at the parent2 item boundary, not mid-item: {:?}..{:?}",
            pieces[2].body.lines().next(),
            pieces[2].body.lines().last()
        );
    }

    #[test]
    fn crlf_document_with_tab_closed_fence_still_splits_after_heading() {
        // Pins Fix 3: normalize_fence_closer_tabs strips a CRLF line ending as one unit and
        // re-appends it verbatim, so a tab-suffixed closing fence in a CRLF document still
        // closes the fence (rather than leaving it open and swallowing "## Two").
        let root = temp_path("fence-tab-crlf.md");
        fs::write(
            &root,
            "# Doc\r\n## One\r\n```\r\nfenced\r\n```\t\r\n## Two\r\nbody\r\n",
        )
        .unwrap();
        let doc = parse_document(&root, root.parent().unwrap(), &TokenCounter::Test).unwrap();
        assert_eq!(
            doc.sections
                .iter()
                .map(|section| section.headings.last().unwrap().as_str())
                .collect::<Vec<_>>(),
            vec!["One", "Two"]
        );
        let _ = fs::remove_file(root);
    }

    #[test]
    fn normalize_fence_closer_tabs_preserves_byte_length_on_crlf() {
        let text = "```\t\r\nfenced\r\n```\t\r\n";
        assert_eq!(normalize_fence_closer_tabs(text).len(), text.len());
    }

    #[test]
    fn shims_preserve_byte_length_round_trip() {
        // Pins Fix 4: both shims (and parser_input's composition of them) must never change
        // the input's byte length, since every downstream Span depends on byte offsets from
        // the shimmed text mapping through line_offsets(original) to the same source line. The
        // CJK/emoji frontmatter case is sharpest: neutralize_front_matter dot-fills byte-by-
        // byte, so a multi-byte UTF-8 character replaced by a single-byte '.' per byte is the
        // path most likely to silently shrink the output if that per-byte loop regressed to
        // per-character.
        let no_trailing_newline = "# Doc\n## One\n```\t";
        assert_eq!(
            normalize_fence_closer_tabs(no_trailing_newline).len(),
            no_trailing_newline.len()
        );
        assert_eq!(
            parser_input(no_trailing_newline).len(),
            no_trailing_newline.len()
        );

        let empty_fence_suffix = "# Doc\n## One\n```\nfenced\n```\n";
        assert_eq!(
            normalize_fence_closer_tabs(empty_fence_suffix).len(),
            empty_fence_suffix.len()
        );

        let cjk_emoji_frontmatter =
            "---\ntitle: \u{65e5}\u{672c}\u{8a9e}\u{306e}\u{30bf}\u{30a4}\u{30c8}\u{30eb}\nemoji: \u{1f389}\u{1f9c0}\n---\n# Heading\nbody\n";
        assert_eq!(
            neutralize_front_matter(cjk_emoji_frontmatter).len(),
            cjk_emoji_frontmatter.len()
        );
        assert_eq!(
            parser_input(cjk_emoji_frontmatter).len(),
            cjk_emoji_frontmatter.len()
        );

        let composed = "---\ntitle: \u{7d75}\u{6587}\u{5b57} \u{1f389}\n---\n## One\n```\t\nfenced\n```\t\n## Two\nbody\n";
        assert_eq!(parser_input(composed).len(), composed.len());
    }

    #[test]
    fn thematic_break_dash_line_is_not_mistaken_for_front_matter() {
        // Pins Fix 5 shape 1: a document opening with a THEMATIC BREAK "---" (no preceding
        // paragraph, so pulldown-cmark reads it as a horizontal rule, not frontmatter) must not
        // be neutralized. is_yaml_line_shape rejects the 2+-`#` ATX heading inside it, which
        // aborts the scan before any dot-filling happens.
        let text = "---\n## Real Heading\nbody\n\n---\nmore\n";
        assert_eq!(neutralize_front_matter(text), text);

        let root = temp_path("thematic-break.md");
        fs::write(&root, text).unwrap();
        let doc = parse_document(&root, root.parent().unwrap(), &TokenCounter::Test).unwrap();
        assert!(doc
            .sections
            .iter()
            .any(|section| section.headings.last().is_some_and(|h| h == "Real Heading")));
        assert!(doc
            .sections
            .iter()
            .any(|section| section.body.contains("body")));
        let _ = fs::remove_file(root);
    }

    #[test]
    fn block_scalar_containing_column_zero_dashes_is_a_known_unfixed_limitation() {
        // Pins Fix 5 shape 2 as a DOCUMENTED, NOT-fixed limitation: distinguishing a YAML block
        // scalar's own content from the real closing "---" needs a YAML parser. "notes: |"
        // opens a block scalar; the "---" at column 0 a few lines down is meant as literal
        // scalar content, but because it carries no leading whitespace, is_block_scalar_key's
        // crude indentation tracking (in_scalar clears on any unindented, non-empty line) reads
        // it as the closing delimiter instead of the real closer two lines further down. Do not
        // "fix" this by making the tracker YAML-aware -- that scope is explicitly out.
        let text = "---\ntitle: x\nnotes: |\n  indented content\n---\n  more scalar text\n---\n# Heading\nbody\n";
        let neutralized = neutralize_front_matter(text);
        let mistaken_closer_end = text.find("---\n  more").unwrap() + "---\n".len();
        let expected_prefix: String = text[..mistaken_closer_end]
            .bytes()
            .map(|byte| {
                if matches!(byte, b'\n' | b'\r') {
                    byte as char
                } else {
                    '.'
                }
            })
            .collect();
        assert_eq!(&neutralized[..mistaken_closer_end], expected_prefix);
        assert_eq!(
            &neutralized[mistaken_closer_end..],
            &text[mistaken_closer_end..]
        );
    }

    #[test]
    fn astro_style_nested_mappings_and_list_of_mappings_are_valid_front_matter() {
        // Regression pin for the phantom-section bug: a genuine Astro/Starlight front-matter
        // block with a nested mapping (`hero:` -> `image:` -> `file:`/`alt:`) and a YAML list
        // of mappings under a key (`actions:` -> `- text: ...` / indented `link:`/`icon:`/
        // `variant:`) must still be recognized and neutralized -- not aborted.
        let text = "---\ntitle: Example\nhero:\n  title: Example\n  image:\n    file: ../a.svg\n    alt: logo\n  actions:\n    - text: Get started\n      link: install/\n      icon: right-arrow\n      variant: primary\n    - text: View on GitHub\n      link: https://example.com\n      icon: external\n      variant: minimal\n---\nbody\n";
        let neutralized = neutralize_front_matter(text);
        assert_ne!(neutralized, text);
        assert_eq!(neutralized.len(), text.len());
        let front_matter_end = text.find("---\nbody").unwrap() + "---\n".len();
        assert!(neutralized[..front_matter_end]
            .bytes()
            .all(|byte| matches!(byte, b'.' | b'\n' | b'\r')));
        assert_eq!(&neutralized[front_matter_end..], &text[front_matter_end..]);
    }
}
