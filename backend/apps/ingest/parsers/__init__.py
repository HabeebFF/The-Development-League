"""One parser per Free Fire observer file type.

- ``filenames``: classify an uploaded file by name (kind, match id, timestamp)
- ``match_id``: ``MatchId_*.log``
- ``safe_zone``: ``SafeZone_*.log``
- ``match_result``: ``MatchResult_*.log``
- ``replay_info``: ``ReplayInfo_*.json`` (the ``.bin`` is stored, not parsed)
- ``debugger``: ``debugger-*.log`` (streamed, split into matches)
- ``names``: raw / display / search forms of in-game names
"""
