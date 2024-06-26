from pathlib import Path
from crytic_compile import CryticCompile
from crytic_compile.platform.solc_standard_json import SolcStandardJson

from slither import Slither
from slither.slithir.operations import InternalCall, LibraryCall

from tests.utils import _run_all_detectors

TEST_DATA_DIR = Path(__file__).resolve().parent / "test_data"
USING_FOR_TEST_DATA_DIR = Path(TEST_DATA_DIR, "using_for")


def test_using_for_global_collision(solc_binary_path) -> None:
    solc_path = solc_binary_path("0.8.15")
    standard_json = SolcStandardJson()
    for source_file in Path(USING_FOR_TEST_DATA_DIR, "using_for_global_collision").rglob("*.sol"):
        standard_json.add_source_file(Path(source_file).as_posix())
    compilation = CryticCompile(standard_json, solc=solc_path)
    sl = Slither(compilation, disallow_partial=True)
    _run_all_detectors(sl)


def test_using_for_top_level_same_name(solc_binary_path) -> None:
    solc_path = solc_binary_path("0.8.15")
    slither = Slither(
        Path(USING_FOR_TEST_DATA_DIR, "using-for-3-0.8.0.sol").as_posix(), solc=solc_path
    )
    contract_c = slither.get_contract_from_name("C")[0]
    libCall = contract_c.get_function_from_full_name("libCall(uint256)")
    found = False
    for ir in libCall.all_slithir_operations():
        if isinstance(ir, LibraryCall) and ir.destination == "Lib" and ir.function_name == "a":
            found = True
    assert found


def test_using_for_top_level_implicit_conversion(solc_binary_path) -> None:
    solc_path = solc_binary_path("0.8.15")
    slither = Slither(
        Path(USING_FOR_TEST_DATA_DIR, "using-for-4-0.8.0.sol").as_posix(), solc=solc_path
    )
    contract_c = slither.get_contract_from_name("C")[0]
    libCall = contract_c.get_function_from_full_name("libCall(uint16)")
    found = False
    for ir in libCall.all_slithir_operations():
        if isinstance(ir, LibraryCall) and ir.destination == "Lib" and ir.function_name == "f":
            found = True
    assert found


def test_using_for_alias_top_level(solc_binary_path) -> None:
    solc_path = solc_binary_path("0.8.15")
    slither = Slither(
        Path(USING_FOR_TEST_DATA_DIR, "using-for-alias-top-level-0.8.0.sol").as_posix(),
        solc=solc_path,
    )
    contract_c = slither.get_contract_from_name("C")[0]
    libCall = contract_c.get_function_from_full_name("libCall(uint256)")
    found = False
    for ir in libCall.all_slithir_operations():
        if isinstance(ir, LibraryCall) and ir.destination == "Lib" and ir.function_name == "b":
            found = True
    assert found

    found = False
    topLevelCall = contract_c.get_function_from_full_name("topLevel(uint256)")
    for ir in topLevelCall.all_slithir_operations():
        if isinstance(ir, InternalCall) and ir.function_name == "a":
            found = True
    assert found


def test_using_for_alias_contract(solc_binary_path) -> None:
    solc_path = solc_binary_path("0.8.15")
    slither = Slither(
        Path(USING_FOR_TEST_DATA_DIR, "using-for-alias-contract-0.8.0.sol").as_posix(),
        solc=solc_path,
    )
    contract_c = slither.get_contract_from_name("C")[0]
    libCall = contract_c.get_function_from_full_name("libCall(uint256)")
    found = False
    for ir in libCall.all_slithir_operations():
        if isinstance(ir, LibraryCall) and ir.destination == "Lib" and ir.function_name == "b":
            found = True

    assert found

    found = False
    topLevelCall = contract_c.get_function_from_full_name("topLevel(uint256)")
    for ir in topLevelCall.all_slithir_operations():
        if isinstance(ir, InternalCall) and ir.function_name == "a":
            found = True
    assert found


def test_using_for_in_library(solc_binary_path) -> None:
    solc_path = solc_binary_path("0.8.15")
    slither = Slither(
        Path(USING_FOR_TEST_DATA_DIR, "using-for-in-library-0.8.0.sol").as_posix(), solc=solc_path
    )
    contract_c = slither.get_contract_from_name("A")[0]
    libCall = contract_c.get_function_from_full_name("a(uint256)")
    found = False
    for ir in libCall.all_slithir_operations():
        if isinstance(ir, LibraryCall) and ir.destination == "B" and ir.function_name == "b":
            found = True
    assert found


def test_using_for_constant_folding(slither_from_solidity_source) -> None:
    # https://github.com/crytic/slither/issues/2307
    source = """
            library SafeMath {
            uint256 private constant twelve = 12; 
            struct A {uint256 a;}
            function add(A[twelve] storage z) internal { }
        }

        contract MathContract {
            uint256 private constant twelve = 12; 
            using SafeMath for SafeMath.A[twelve];
            SafeMath.A[twelve] public z;
            function safeAdd() public {
                z.add();
            }
        }
    """
    with slither_from_solidity_source(source) as slither:
        contract = slither.get_contract_from_name("MathContract")[0]
        add = contract.get_function_from_full_name("safeAdd()")
        found = False
        for ir in add.all_slithir_operations():
            if isinstance(ir, LibraryCall) and ir.function_name == "add":
                found = True
        assert found
