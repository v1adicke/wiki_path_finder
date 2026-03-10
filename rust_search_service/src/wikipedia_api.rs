use reqwest::Client;
use rustc_hash::FxHashSet;
use serde_json::Value;

type FastSet<T> = FxHashSet<T>;

pub async fn fetch_links_uncached(
    client: Client,
    title: String,
) -> Result<Vec<String>, reqwest::Error> {
    let mut plcontinue: Option<String> = None;
    let mut out: Vec<String> = Vec::new();

    loop {
        let mut params: Vec<(&str, String)> = vec![
            ("action", "query".to_string()),
            ("format", "json".to_string()),
            ("formatversion", "2".to_string()),
            ("titles", title.clone()),
            ("prop", "links".to_string()),
            ("plnamespace", "0".to_string()),
            ("pllimit", "max".to_string()),
        ];
        if let Some(token) = &plcontinue {
            params.push(("plcontinue", token.clone()));
        }

        let data = client
            .get("https://ru.wikipedia.org/w/api.php")
            .query(&params)
            .send()
            .await?
            .json::<Value>()
            .await?;

        if let Some(pages) = data
            .get("query")
            .and_then(|q| q.get("pages"))
            .and_then(|p| p.as_array())
        {
            for page in pages {
                if let Some(links) = page.get("links").and_then(|l| l.as_array()) {
                    for link in links {
                        if let Some(link_title) = link.get("title").and_then(|t| t.as_str()) {
                            out.push(link_title.to_string());
                        }
                    }
                }
            }
        }

        plcontinue = data
            .get("continue")
            .and_then(|c| c.get("plcontinue"))
            .and_then(|v| v.as_str())
            .map(ToOwned::to_owned);

        if plcontinue.is_none() {
            break;
        }
    }

    Ok(out)
}

pub async fn fetch_backlinks_uncached(
    client: Client,
    title: String,
) -> Result<Vec<String>, reqwest::Error> {
    let mut blcontinue: Option<String> = None;
    let mut out: Vec<String> = Vec::new();

    loop {
        let mut params: Vec<(&str, String)> = vec![
            ("action", "query".to_string()),
            ("format", "json".to_string()),
            ("formatversion", "2".to_string()),
            ("list", "backlinks".to_string()),
            ("bltitle", title.clone()),
            ("blnamespace", "0".to_string()),
            ("bllimit", "max".to_string()),
        ];
        if let Some(token) = &blcontinue {
            params.push(("blcontinue", token.clone()));
        }

        let data = client
            .get("https://ru.wikipedia.org/w/api.php")
            .query(&params)
            .send()
            .await?
            .json::<Value>()
            .await?;

        if let Some(backlinks) = data
            .get("query")
            .and_then(|q| q.get("backlinks"))
            .and_then(|b| b.as_array())
        {
            for backlink in backlinks {
                if let Some(backlink_title) = backlink.get("title").and_then(|t| t.as_str()) {
                    out.push(backlink_title.to_string());
                }
            }
        }

        blcontinue = data
            .get("continue")
            .and_then(|c| c.get("blcontinue"))
            .and_then(|v| v.as_str())
            .map(ToOwned::to_owned);

        if blcontinue.is_none() {
            break;
        }
    }

    Ok(out)
}

pub fn dedupe(items: Vec<String>) -> Vec<String> {
    let mut seen: FastSet<String> = FastSet::default();
    let mut out: Vec<String> = Vec::new();
    for item in items {
        if seen.insert(item.clone()) {
            out.push(item);
        }
    }
    out
}
