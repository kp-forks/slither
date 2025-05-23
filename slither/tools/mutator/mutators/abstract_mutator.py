import abc
import logging
from pathlib import Path
from typing import Optional, Dict, Tuple, List, Union
from slither.core.compilation_unit import SlitherCompilationUnit
from slither.formatters.utils.patches import apply_patch, create_diff
from slither.tools.mutator.utils.testing_generated_mutant import test_patch
from slither.core.declarations import Contract
from slither.utils.colors import red

logger = logging.getLogger("Slither-Mutate")


class IncorrectMutatorInitialization(Exception):
    pass


class AbstractMutator(
    metaclass=abc.ABCMeta
):  # pylint: disable=too-few-public-methods,too-many-instance-attributes
    NAME = ""
    HELP = ""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        compilation_unit: SlitherCompilationUnit,
        timeout: int,
        testing_command: str,
        testing_directory: str,
        contract_instance: Contract,
        solc_remappings: Union[str, None],
        verbose: bool,
        output_folder: Path,
        dont_mutate_line: List[int],
        rate: int = 10,
        seed: Optional[int] = None,
    ) -> None:
        self.compilation_unit = compilation_unit
        self.slither = compilation_unit.core
        self.seed = seed
        self.rate = rate
        self.test_command = testing_command
        self.test_directory = testing_directory
        self.timeout = timeout
        self.solc_remappings = solc_remappings
        self.verbose = verbose
        self.output_folder = output_folder
        self.contract = contract_instance
        self.in_file = self.contract.source_mapping.filename.absolute
        self.dont_mutate_line = dont_mutate_line
        # total revert/comment/tweak mutants that were generated and compiled
        self.total_mutant_counts = [0, 0, 0]
        # total uncaught revert/comment/tweak mutants
        self.uncaught_mutant_counts = [0, 0, 0]

        if not self.NAME:
            raise IncorrectMutatorInitialization(
                f"NAME is not initialized {self.__class__.__name__}"
            )

        if not self.HELP:
            raise IncorrectMutatorInitialization(
                f"HELP is not initialized {self.__class__.__name__}"
            )

        if rate < 0 or rate > 100:
            raise IncorrectMutatorInitialization(
                f"rate must be between 0 and 100 {self.__class__.__name__}"
            )

    def should_mutate_node(self, node) -> bool:
        return (
            not node.source_mapping.lines[0] in self.dont_mutate_line
            and node.source_mapping.filename.absolute == self.in_file
        )

    @abc.abstractmethod
    def _mutate(self) -> Dict:
        """Abstract placeholder, will be overwritten by each mutator"""
        return {}

    # pylint: disable=too-many-branches
    def mutate(self) -> Tuple[List[int], List[int], List[int]]:
        all_patches: Dict = {}
        # pylint: disable=broad-exception-caught
        try:
            # call _mutate function from different mutators
            (all_patches) = self._mutate()
        except Exception as e:
            logger.error(red("%s mutator failed in %s: %s"), self.NAME, self.contract.name, str(e))
        if "patches" not in all_patches:
            logger.debug("No patches found by %s", self.NAME)
            return [0, 0, 0], [0, 0, 0], self.dont_mutate_line

        for file in all_patches["patches"]:  # Note: This should only loop over a single file
            original_txt = self.slither.source_code[file].encode("utf8")
            patches = all_patches["patches"][file]
            patches.sort(key=lambda x: x["start"])
            for patch in patches:
                # test the patch
                patchWasCaught = test_patch(
                    self.output_folder,
                    file,
                    patch,
                    self.test_command,
                    self.NAME,
                    self.timeout,
                    self.solc_remappings,
                    self.verbose,
                )

                # count the uncaught mutants, flag RR/CR mutants to skip further mutations
                if patchWasCaught == 0:
                    if self.NAME == "RR":
                        self.uncaught_mutant_counts[0] += 1
                        self.dont_mutate_line.append(patch["line_number"])
                    elif self.NAME == "CR":
                        self.uncaught_mutant_counts[1] += 1
                        self.dont_mutate_line.append(patch["line_number"])
                    else:
                        self.uncaught_mutant_counts[2] += 1

                    patched_txt, _ = apply_patch(original_txt, patch, 0)
                    diff = create_diff(self.compilation_unit, original_txt, patched_txt, file)
                    if not diff:
                        logger.info(f"Impossible to generate patch; empty {patches}")

                    # add uncaught mutant patches to a output file
                    with (self.output_folder / "patches_files.txt").open(
                        "a", encoding="utf8"
                    ) as patches_file:
                        patches_file.write(diff + "\n")

                # count the total number of mutants that we were able to compile
                if patchWasCaught != 2:
                    if self.NAME == "RR":
                        self.total_mutant_counts[0] += 1
                    elif self.NAME == "CR":
                        self.total_mutant_counts[1] += 1
                    else:
                        self.total_mutant_counts[2] += 1

        return self.total_mutant_counts, self.uncaught_mutant_counts, self.dont_mutate_line
