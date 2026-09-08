use super::*;
use std::io::{BufRead, BufReader, Write};

#[test]
#[ignore = "requires the standalone ASan/UBSan C driver in WSH_GIT_PARSER_TEST_DRIVER"]
fn native_parser_matches_retained_rust_parser() {
    let driver = std::env::var_os("WSH_GIT_PARSER_TEST_DRIVER").expect("C driver path");
    let mut child = Command::new(driver)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .unwrap();
    let mut input = child.stdin.take().unwrap();
    let mut output = BufReader::new(child.stdout.take().unwrap());
    let seeds: &[&[u8]] = &[
        b"",
        b"1 .M x\n2 R. x\nu UU x\n? file\n",
        b"# branch.ab +18446744073709551615 -18446744073709551615\n",
        b"# branch.ab +18446744073709551616 -18446744073709551616\n",
        b"# branch.ab +00000000000000000000000000000000000001 -00002\n",
        b"# branch.ab ++1 --2\n",
        b"# branch.ab +1 -2\r\n",
        b"1 .\r",
        b"1 .\r\n",
        b"1 \xc2\xa0M.\n",
        b"1 \xe2\x80\xaf.M\n# branch.ab \xc2\x85+4 \xe3\x80\x80-9\n",
        b"\xf0\x90\x80",
        b"\xed\xa0\x80",
        b"\xe2\x82x",
        b"a\0b",
    ];
    let mut random = 0x81fca137u64;
    for case in 0..10015 {
        let mut data = seeds[case % seeds.len()].to_vec();
        if case >= seeds.len() {
            for _ in 0..(case % 9 + 1) {
                random ^= random << 13;
                random ^= random >> 7;
                random ^= random << 17;
                let position = random as usize % (data.len() + 1);
                if position == data.len() {
                    data.push((random >> 32) as u8);
                } else {
                    data[position] = (random >> 32) as u8;
                }
            }
        }
        writeln!(input, "{}", encode_hex(&data)).unwrap();
        input.flush().unwrap();
        let mut line = String::new();
        assert!(output.read_line(&mut line).unwrap() > 0);
        let fields: Vec<_> = line.trim_end_matches('\n').split('|').collect();
        assert_eq!(fields.len(), 4);
        let identity = RepositoryIdentity {
            root: PathBuf::from("/"),
            git_dir: PathBuf::from("/dev/null/wsh-no-git"),
            common_git_dir: PathBuf::from("/dev/null/wsh-no-git"),
            branch: Some("test".into()),
            head_oid: None,
        };
        let expected = match parse_git_status(Path::new("/"), 1, identity, &data) {
            Ok(s) => format!(
                "0 {} {} {} {} {}",
                i32::from(s.staged),
                i32::from(s.modified),
                i32::from(s.untracked),
                s.ahead,
                s.behind
            ),
            Err(_) => "-1 0 0 0 0 0".into(),
        };
        assert_eq!(fields[0], expected, "case {case}: {}", encode_hex(&data));
        let end = data.iter().position(|&b| b == 0).unwrap_or(data.len());
        let lossy = String::from_utf8_lossy(&data[..end]);
        assert_eq!(fields[1], encode_hex(lossy.as_bytes()), "lossy case {case}");
        assert_eq!(
            fields[2],
            encode_hex(lossy.trim().as_bytes()),
            "trim case {case}"
        );
        let records = std::str::from_utf8(&data)
            .ok()
            .filter(|_| !data.contains(&0))
            .map(|s| s.lines().count() as i32)
            .unwrap_or(-1);
        assert_eq!(fields[3], records.to_string(), "packed records case {case}");
    }
    drop(input);
    assert!(child.wait().unwrap().success());
}
