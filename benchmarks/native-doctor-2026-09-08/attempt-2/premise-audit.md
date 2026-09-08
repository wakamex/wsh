# Global startup mismatch in the first doctor comparison

The first doctor comparison measured different effective configuration. Rust forces `-d`; the native candidate preserves global startup. Strace directly shows the native child sourcing Fedora's `/etc/zshrc` and `/etc/profile.d` programs. Median native time was 65.528 ms versus 12.211 ms for Rust, with a +55.335 ms paired p95 difference.

The next comparison will leave both implementations unchanged and put `unsetopt globalrcs` in the shared fixture's `.zshenv`. This reproduces the baseline's global-file policy without suppressing real global startup in the product. The +3 ms paired p95 threshold and 50 alternating pairs remain unchanged. Existing first-run real-OMZ behavior checks with native global startup remain retained. A separate correctness fixture will verify that native doctor actually includes a global ownership setting.
