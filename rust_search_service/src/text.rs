use once_cell::sync::Lazy;
use regex::Regex;
use rustc_hash::FxHashSet;

static TOKEN_RE: Lazy<Regex> =
    Lazy::new(|| Regex::new(r"[\w\-]+").expect("token regex build failed"));

type FastSet<T> = FxHashSet<T>;

pub fn normalize_title(value: &str) -> String {
    value
        .trim()
        .replace('_', " ")
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
}

pub fn tokenize_title(title: &str) -> FastSet<String> {
    TOKEN_RE
        .find_iter(&title.to_lowercase())
        .map(|m| m.as_str().to_string())
        .filter(|token| token.len() > 2)
        .collect()
}
