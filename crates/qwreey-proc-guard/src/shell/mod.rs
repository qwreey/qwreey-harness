//! Bash 명령 글 읽기: 구간 나누기(`hooks/shell_segments.py`)와 python shlex 낱말 읽기.

pub mod segments;
pub mod shlex;

pub use segments::{Segment, segments, strip_heredocs};
