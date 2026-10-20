from pydantic import BaseModel, Field

class RegisterWrite(BaseModel):
    """One RFFE register field/setting, e.g. PA enable."""
    address: str                      # "0x1C"
    field: str = ""                   # "PA_EN" / bits "[3]"
    value: str = ""                   # "0x1" / "1"
    purpose: str = ""                 # "PA on, Band B3 TX"
    raw: str = ""                     # source table row, for human audit
    page: int | None = None

class RfPath(BaseModel):
    """One switch/filter routing state from a truth/state table."""
    state: str = ""                   # "State 5" / mode name
    input_pin: str = ""               # "RFIN2"
    output_pin: str = ""              # "ANT1" / "RFOUT"
    band: str = ""                    # "B3" / "n78" / "1.7-2.0 GHz"
    control: str = ""                 # raw control bits / register refs
    page: int | None = None

class RfConfig(BaseModel):
    part_number: str = ""
    vendor: str = ""                  # Qorvo / Skyworks / Qualcomm / ...
    rffe_usid: str = ""               # MIPI RFFE slave USID if stated
    registers: list[RegisterWrite] = Field(default_factory=list)
    rf_paths: list[RfPath] = Field(default_factory=list)
    pins: dict[str, str] = Field(default_factory=dict)  # pin no -> name/function
    needs_review: bool = True         # never auto-trust for hardware bring-up
