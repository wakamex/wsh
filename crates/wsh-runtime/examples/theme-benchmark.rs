//! Retained comparison driver; never installed into a bundle.
use std::io::{BufRead, BufReader, Write};
use std::process::{Command, Stdio};
use std::time::Instant;

fn main() {
    let mut args = std::env::args_os().skip(1);
    let driver = args.next().expect("C benchmark driver");
    let mut samples = Vec::new();
    for path in args {
        let source = std::fs::read_to_string(&path).unwrap();
        let theme = path.to_string_lossy().into_owned();
        let mut child = Command::new(&driver)
            .arg(&path)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .spawn()
            .unwrap();
        let mut input = child.stdin.take().unwrap();
        let mut output = BufReader::new(child.stdout.take().unwrap());
        for mode in ["empty", "parse"] {
            for pair in 0..1001 {
                let order = if pair % 2 == 0 {
                    ["rust", "c"]
                } else {
                    ["c", "rust"]
                };
                for variant in order {
                    let elapsed = if variant == "rust" {
                        let started = Instant::now();
                        if mode == "parse" {
                            drop(std::hint::black_box(
                                wsh_runtime::parse_theme(&source).unwrap(),
                            ));
                        }
                        started.elapsed().as_nanos() as u64
                    } else {
                        writeln!(input, "{}", if mode == "parse" { "p" } else { "e" }).unwrap();
                        input.flush().unwrap();
                        let mut line = String::new();
                        assert!(output.read_line(&mut line).unwrap() > 0);
                        line.trim().parse::<u64>().unwrap()
                    };
                    if pair > 0 {
                        samples.push(serde_json::json!({"theme": theme, "mode": mode, "pair": pair - 1, "variant": variant, "elapsed_ns": elapsed}));
                    }
                }
            }
        }
        drop(input);
        assert!(child.wait().unwrap().success());
    }
    println!("{}", serde_json::to_string_pretty(&samples).unwrap());
}
