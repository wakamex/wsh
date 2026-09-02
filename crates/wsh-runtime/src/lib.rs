use std::collections::HashSet;
use std::fs;
use std::io::{BufRead, Write};
use std::path::Path;

use serde::{Deserialize, Serialize};

const MAX_THEME_BYTES: u64 = 64 * 1024;
const MAX_PROTOCOL_LINE_BYTES: usize = 64 * 1024;
const MAX_LITERAL_CHARS: usize = 128;

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields, rename_all = "kebab-case")]
pub struct Theme {
    pub schema_version: u32,
    pub id: String,
    pub name: String,
    pub left: Vec<Component>,
    pub right: Vec<Component>,
    pub context: ContextComponent,
    pub cwd: CwdComponent,
    pub git: GitComponent,
    pub duration: DurationComponent,
    pub prompt_character: PromptCharacterComponent,
}

#[derive(Debug, Clone, Copy, Deserialize, PartialEq, Eq, Hash)]
#[serde(rename_all = "kebab-case")]
pub enum Component {
    Context,
    Cwd,
    Git,
    Duration,
    PromptCharacter,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields, rename_all = "kebab-case")]
pub struct ContextComponent {
    pub enabled: bool,
    pub show_local: bool,
    pub show_ssh: bool,
    pub separator: String,
    pub suffix: String,
    pub color: Color,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields, rename_all = "kebab-case")]
pub struct CwdComponent {
    pub enabled: bool,
    pub style: CwdStyle,
    pub home_symbol: String,
    pub color: Color,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum CwdStyle {
    Full,
    Short,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields, rename_all = "kebab-case")]
pub struct GitComponent {
    pub enabled: bool,
    pub hide_branches: Vec<String>,
    pub prefix: String,
    pub separator: String,
    pub color: Color,
    pub symbols: GitSymbols,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields, rename_all = "kebab-case")]
pub struct GitSymbols {
    pub branch: String,
    pub detached: String,
    pub staged: String,
    pub modified: String,
    pub untracked: String,
    pub ahead: String,
    pub behind: String,
    pub diverged: String,
    pub rebase: String,
    pub merge: String,
    pub cherry_pick: String,
    pub revert: String,
    pub bisect: String,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields, rename_all = "kebab-case")]
pub struct DurationComponent {
    pub enabled: bool,
    pub threshold_ms: u64,
    pub prefix: String,
    pub suffix: String,
    pub color: Color,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields, rename_all = "kebab-case")]
pub struct PromptCharacterComponent {
    pub enabled: bool,
    pub success: String,
    pub failure: String,
    pub privileged: String,
    pub success_color: Color,
    pub failure_color: Color,
    pub privileged_color: Color,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Color {
    Default,
    Black,
    Red,
    Green,
    Yellow,
    Blue,
    Magenta,
    Cyan,
    White,
    BrightBlack,
    BrightRed,
    BrightGreen,
    BrightYellow,
    BrightBlue,
    BrightMagenta,
    BrightCyan,
    BrightWhite,
}

#[derive(Debug, Deserialize)]
#[serde(tag = "type", rename_all = "kebab-case", deny_unknown_fields)]
enum Request {
    Ping { version: u32, id: u64 },
    Shutdown { version: u32, id: u64 },
}

#[derive(Serialize)]
struct Ready<'a> {
    version: u32,
    #[serde(rename = "type")]
    message_type: &'static str,
    theme: &'a str,
}

#[derive(Serialize)]
struct Response<'a> {
    version: u32,
    #[serde(rename = "type")]
    message_type: &'a str,
    id: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    error: Option<&'a str>,
}

pub fn load_theme(path: &Path) -> Result<Theme, String> {
    let metadata = fs::symlink_metadata(path)
        .map_err(|error| format!("could not inspect theme {}: {error}", path.display()))?;
    if !metadata.file_type().is_file() || metadata.file_type().is_symlink() {
        return Err("theme must be a regular file".into());
    }
    if metadata.len() > MAX_THEME_BYTES {
        return Err(format!("theme exceeds {MAX_THEME_BYTES} bytes"));
    }
    let source = fs::read_to_string(path)
        .map_err(|error| format!("could not read theme {}: {error}", path.display()))?;
    parse_theme(&source)
}

pub fn parse_theme(source: &str) -> Result<Theme, String> {
    let theme: Theme = toml::from_str(source).map_err(|error| format!("invalid theme: {error}"))?;
    validate_theme(&theme)?;
    Ok(theme)
}

pub fn serve<R: BufRead, W: Write>(
    theme: Theme,
    mut input: R,
    mut output: W,
) -> Result<(), String> {
    write_json(
        &mut output,
        &Ready {
            version: 1,
            message_type: "ready",
            theme: &theme.id,
        },
    )?;

    loop {
        let Some(line) = read_line_bounded(&mut input, MAX_PROTOCOL_LINE_BYTES)? else {
            return Ok(());
        };
        let request = match serde_json::from_slice::<Request>(&line) {
            Ok(request) => request,
            Err(_) => {
                write_json(
                    &mut output,
                    &Response {
                        version: 1,
                        message_type: "error",
                        id: None,
                        error: Some("malformed request"),
                    },
                )?;
                continue;
            }
        };
        match request {
            Request::Ping { version: 1, id } => write_json(
                &mut output,
                &Response {
                    version: 1,
                    message_type: "pong",
                    id: Some(id),
                    error: None,
                },
            )?,
            Request::Shutdown { version: 1, id } => {
                write_json(
                    &mut output,
                    &Response {
                        version: 1,
                        message_type: "stopping",
                        id: Some(id),
                        error: None,
                    },
                )?;
                return Ok(());
            }
            Request::Ping { id, .. } | Request::Shutdown { id, .. } => write_json(
                &mut output,
                &Response {
                    version: 1,
                    message_type: "error",
                    id: Some(id),
                    error: Some("unsupported protocol version"),
                },
            )?,
        }
    }
}

fn validate_theme(theme: &Theme) -> Result<(), String> {
    if theme.schema_version != 1 {
        return Err(format!(
            "unsupported theme schema version: {}",
            theme.schema_version
        ));
    }
    validate_identifier("id", &theme.id)?;
    validate_literal("name", &theme.name)?;

    let mut components = HashSet::new();
    for component in theme.left.iter().chain(&theme.right) {
        if !components.insert(*component) {
            return Err(format!("component appears more than once: {component:?}"));
        }
    }
    if !components.contains(&Component::PromptCharacter) || !theme.prompt_character.enabled {
        return Err("prompt-character must be enabled and present in the layout".into());
    }
    for (component, enabled) in [
        (Component::Context, theme.context.enabled),
        (Component::Cwd, theme.cwd.enabled),
        (Component::Git, theme.git.enabled),
        (Component::Duration, theme.duration.enabled),
        (Component::PromptCharacter, theme.prompt_character.enabled),
    ] {
        if components.contains(&component) != enabled {
            return Err(format!(
                "layout and enabled state disagree for {component:?}"
            ));
        }
    }
    if theme.git.hide_branches.len() > 16 {
        return Err("git.hide-branches exceeds 16 entries".into());
    }
    for branch in &theme.git.hide_branches {
        validate_literal("git.hide-branches", branch)?;
    }
    for (name, literal) in literals(theme) {
        validate_literal(name, literal)?;
    }
    Ok(())
}

fn literals(theme: &Theme) -> Vec<(&'static str, &str)> {
    vec![
        ("context.separator", &theme.context.separator),
        ("context.suffix", &theme.context.suffix),
        ("cwd.home-symbol", &theme.cwd.home_symbol),
        ("git.prefix", &theme.git.prefix),
        ("git.separator", &theme.git.separator),
        ("git.symbols.branch", &theme.git.symbols.branch),
        ("git.symbols.detached", &theme.git.symbols.detached),
        ("git.symbols.staged", &theme.git.symbols.staged),
        ("git.symbols.modified", &theme.git.symbols.modified),
        ("git.symbols.untracked", &theme.git.symbols.untracked),
        ("git.symbols.ahead", &theme.git.symbols.ahead),
        ("git.symbols.behind", &theme.git.symbols.behind),
        ("git.symbols.diverged", &theme.git.symbols.diverged),
        ("git.symbols.rebase", &theme.git.symbols.rebase),
        ("git.symbols.merge", &theme.git.symbols.merge),
        ("git.symbols.cherry-pick", &theme.git.symbols.cherry_pick),
        ("git.symbols.revert", &theme.git.symbols.revert),
        ("git.symbols.bisect", &theme.git.symbols.bisect),
        ("duration.prefix", &theme.duration.prefix),
        ("duration.suffix", &theme.duration.suffix),
        ("prompt-character.success", &theme.prompt_character.success),
        ("prompt-character.failure", &theme.prompt_character.failure),
        (
            "prompt-character.privileged",
            &theme.prompt_character.privileged,
        ),
    ]
}

fn validate_identifier(name: &str, value: &str) -> Result<(), String> {
    if value.is_empty()
        || value.len() > 64
        || !value
            .bytes()
            .all(|byte| byte.is_ascii_lowercase() || byte.is_ascii_digit() || byte == b'-')
    {
        return Err(format!("{name} is not a lowercase ASCII identifier"));
    }
    Ok(())
}

fn validate_literal(name: &str, value: &str) -> Result<(), String> {
    if value.chars().count() > MAX_LITERAL_CHARS || value.chars().any(char::is_control) {
        return Err(format!("{name} is too long or contains control characters"));
    }
    Ok(())
}

fn read_line_bounded<R: BufRead>(reader: &mut R, limit: usize) -> Result<Option<Vec<u8>>, String> {
    let mut line = Vec::new();
    loop {
        let available = reader
            .fill_buf()
            .map_err(|error| format!("could not read request: {error}"))?;
        if available.is_empty() {
            return if line.is_empty() {
                Ok(None)
            } else {
                Ok(Some(line))
            };
        }
        let count = available
            .iter()
            .position(|byte| *byte == b'\n')
            .map_or(available.len(), |position| position + 1);
        if line.len() + count > limit {
            return Err(format!("protocol line exceeds {limit} bytes"));
        }
        line.extend_from_slice(&available[..count]);
        reader.consume(count);
        if line.last() == Some(&b'\n') {
            line.pop();
            if line.last() == Some(&b'\r') {
                line.pop();
            }
            return Ok(Some(line));
        }
    }
}

fn write_json<W: Write, T: Serialize>(writer: &mut W, value: &T) -> Result<(), String> {
    serde_json::to_writer(&mut *writer, value)
        .map_err(|error| format!("could not encode response: {error}"))?;
    writer
        .write_all(b"\n")
        .map_err(|error| format!("could not write response: {error}"))?;
    writer
        .flush()
        .map_err(|error| format!("could not flush response: {error}"))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;

    const VALID_THEME: &str = include_str!("../../../themes/minimal.toml");

    #[test]
    fn parses_the_bundled_minimal_theme() {
        let theme = parse_theme(VALID_THEME).unwrap();
        assert_eq!(theme.id, "minimal");
    }

    #[test]
    fn rejects_unknown_theme_fields() {
        let source = VALID_THEME.replace(
            "schema-version = 1",
            "schema-version = 1\nshell = \"echo unsafe\"",
        );
        assert!(parse_theme(&source).is_err());
    }

    #[test]
    fn rejects_control_characters_in_literals() {
        let source = VALID_THEME.replace("success = \"%\"", "success = \"\\u001b[31m%\"");
        assert!(parse_theme(&source).is_err());
    }

    #[test]
    fn serves_versioned_ping_and_shutdown() {
        let theme = parse_theme(VALID_THEME).unwrap();
        let input = Cursor::new(
            b"{\"type\":\"ping\",\"version\":1,\"id\":7}\n{\"type\":\"shutdown\",\"version\":1,\"id\":8}\n",
        );
        let mut output = Vec::new();
        serve(theme, input, &mut output).unwrap();
        let output = String::from_utf8(output).unwrap();
        assert!(output.contains("\"type\":\"ready\""));
        assert!(output.contains("\"type\":\"pong\",\"id\":7"));
        assert!(output.contains("\"type\":\"stopping\",\"id\":8"));
    }

    #[test]
    fn rejects_oversized_protocol_lines_without_unbounded_read() {
        let mut input = Cursor::new(vec![b'x'; MAX_PROTOCOL_LINE_BYTES + 1]);
        assert!(read_line_bounded(&mut input, MAX_PROTOCOL_LINE_BYTES).is_err());
    }
}
