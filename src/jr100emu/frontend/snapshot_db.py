"""Snapshot metadata management for the debugger overlay."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

SNAPSHOT_DIR = Path("snapshots")
SNAPSHOT_HISTORY_DIR = SNAPSHOT_DIR / "history"
SNAPSHOT_SLOTS = ["slot0", "slot1", "slot2", "slot3"]
DEFAULT_SLOT = SNAPSHOT_SLOTS[0]


@dataclass
class SnapshotMetadata:
    slot: str
    timestamp: float
    comment: str
    path: Path

    def format_timestamp(self) -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.timestamp))


@dataclass
class HistoryEntry:
    slot: str
    timestamp: float
    comment: str
    path: Path

    def format_timestamp(self) -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.timestamp))


class SnapshotDatabase:
    """Manages snapshot metadata stored on disk."""

    def __init__(self) -> None:
        self._slots: Dict[str, SnapshotMetadata] = {}
        self._history: List[HistoryEntry] = []
        self._load_existing()

    def _slot_path(self, slot: str) -> Path:
        return SNAPSHOT_DIR / f"{slot}.json"

    def _meta_path(self, slot: str) -> Path:
        return SNAPSHOT_DIR / f"{slot}.meta.json"

    def _history_path(self, slot: str, timestamp: float) -> Path:
        return SNAPSHOT_HISTORY_DIR / f"{slot}-{int(timestamp * 1000)}.json"

    def _load_existing(self) -> None:
        if not SNAPSHOT_DIR.exists():
            return
        for slot in SNAPSHOT_SLOTS:
            meta_path = self._meta_path(slot)
            if meta_path.exists():
                try:
                    data = json.loads(meta_path.read_text())
                    self._slots[slot] = SnapshotMetadata(
                        slot=slot,
                        timestamp=float(data.get("timestamp", 0.0)),
                        comment=str(data.get("comment", "")),
                        path=self._slot_path(slot),
                    )
                except json.JSONDecodeError:
                    continue
        self._load_history()

    def _load_history(self) -> None:
        self._history = []
        if not SNAPSHOT_HISTORY_DIR.exists():
            return
        for path in SNAPSHOT_HISTORY_DIR.glob("*.json"):
            try:
                data = json.loads(path.read_text())
            except json.JSONDecodeError:
                continue
            slot = data.get("slot")
            timestamp = float(data.get("timestamp", 0.0))
            comment = str(data.get("comment", ""))
            if slot not in SNAPSHOT_SLOTS or timestamp == 0.0:
                continue
            self._history.append(
                HistoryEntry(slot=slot, timestamp=timestamp, comment=comment, path=path)
            )
        self._history.sort(key=lambda entry: entry.timestamp, reverse=True)

    def set_slot(self, slot: str, *, comment: str = "") -> None:
        if slot not in SNAPSHOT_SLOTS:
            raise ValueError("invalid slot")
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        meta = SnapshotMetadata(slot=slot, timestamp=time.time(), comment=comment, path=self._slot_path(slot))
        self._slots[slot] = meta
        self._meta_path(slot).write_text(
            json.dumps({
                "slot": slot,
                "timestamp": meta.timestamp,
                "comment": comment,
            })
        )

    def clear_slot(self, slot: str) -> None:
        self._slots.pop(slot, None)
        meta_path = self._meta_path(slot)
        if meta_path.exists():
            meta_path.unlink()
        self.purge_slot_history(slot)

    def list_slots(self) -> List[SnapshotMetadata]:
        entries = []
        for slot in SNAPSHOT_SLOTS:
            meta = self._slots.get(slot)
            if meta is not None:
                entries.append(meta)
            else:
                entries.append(SnapshotMetadata(slot=slot, timestamp=0.0, comment="(empty)", path=self._slot_path(slot)))
        return entries

    def get(self, slot: str) -> Optional[SnapshotMetadata]:
        return self._slots.get(slot)

    def record_history(self, data: dict, path: Path) -> None:
        entry = HistoryEntry(
            slot=str(data.get("slot")),
            timestamp=float(data.get("timestamp", time.time())),
            comment=str(data.get("comment", "")),
            path=path,
        )
        self._history.insert(0, entry)
        self._history.sort(key=lambda item: item.timestamp, reverse=True)

    def list_history(self, limit: Optional[int] = None) -> List[HistoryEntry]:
        if limit is None:
            return list(self._history)
        return self._history[:limit]

    def purge_slot_history(self, slot: str) -> None:
        remaining = []
        for entry in self._history:
            if entry.slot == slot:
                if entry.path.exists():
                    entry.path.unlink()
            else:
                remaining.append(entry)
        self._history = remaining


__all__ = [
    "SNAPSHOT_DIR",
    "SNAPSHOT_HISTORY_DIR",
    "SNAPSHOT_SLOTS",
    "DEFAULT_SLOT",
    "SnapshotMetadata",
    "HistoryEntry",
    "SnapshotDatabase",
]
