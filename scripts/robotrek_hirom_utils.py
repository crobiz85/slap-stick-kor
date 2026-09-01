"""Small shared 65816/HiROM helpers used by the Robotrek build."""

from __future__ import annotations

TARGET_LENGTH = 0x200000


class Assembler:
    """Minimal 8-bit branch assembler for the generated HiROM stubs."""

    def __init__(self) -> None:
        self.data = bytearray()
        self.labels: dict[str, int] = {}
        self.branches: list[tuple[int, str]] = []

    def emit(self, *values: int) -> None:
        self.data.extend(values)

    def label(self, name: str) -> None:
        if name in self.labels:
            raise ValueError(f"duplicate label: {name}")
        self.labels[name] = len(self.data)

    def branch8(self, opcode: int, label: str) -> None:
        self.emit(opcode, 0)
        self.branches.append((len(self.data) - 1, label))

    def resolve(self) -> bytes:
        for operand_index, label in self.branches:
            if label not in self.labels:
                raise ValueError(f"unknown label: {label}")
            displacement = self.labels[label] - (operand_index + 1)
            if not -128 <= displacement <= 127:
                raise ValueError(f"branch out of range: {label} ({displacement})")
            self.data[operand_index] = displacement & 0xFF
        return bytes(self.data)


def refresh_full_hirom_checksum(target: bytearray) -> int:
    """Write the standard checksum into a physical 2 MiB HiROM image."""

    if len(target) != TARGET_LENGTH:
        raise ValueError("target must be exactly 2 MiB")
    target[0xFFDC:0xFFE0] = b"\x00" * 4
    checksum = (sum(target) + 0x01FE) & 0xFFFF
    complement = checksum ^ 0xFFFF
    target[0xFFDC:0xFFDE] = complement.to_bytes(2, "little")
    target[0xFFDE:0xFFE0] = checksum.to_bytes(2, "little")
    return checksum
