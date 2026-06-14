"""Per-model capability definitions.

Only the VSX-92TXH is described here, but the structure leaves room for other
Pioneer receivers that share the RS-232 protocol.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .const import InputSource


@dataclass(frozen=True)
class ReceiverModel:
    """Capabilities of a particular Pioneer receiver."""

    key: str
    name: str
    input_sources: list[InputSource]
    # Zone 2 supports power, volume and source. Zone 3 is power + source only.
    has_zone_2: bool = True
    has_zone_3: bool = True


VSX_92TXH = ReceiverModel(
    key="vsx_92txh",
    name="VSX-92TXH",
    input_sources=[
        InputSource.PHONO,
        InputSource.CD,
        InputSource.TUNER,
        InputSource.CDR,
        InputSource.DVD,
        InputSource.TV,
        InputSource.VIDEO_1,
        InputSource.MULTI_CH,
        InputSource.VIDEO_2,
        InputSource.DVR_1,
        InputSource.DVR_2,
        InputSource.IPOD,
        InputSource.XM,
        InputSource.HDMI_1,
        InputSource.HDMI_2,
        InputSource.HDMI_3,
        InputSource.BDP,
        InputSource.SIRIUS,
    ],
)

MODELS: dict[str, ReceiverModel] = {VSX_92TXH.key: VSX_92TXH}
