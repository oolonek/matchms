import logging
import os
from collections import OrderedDict
from datetime import datetime
import yaml
import matchms.similarity as mssimilarity
from matchms import calculate_scores
from matchms.importing.load_spectra import load_spectra
from matchms.logging_functions import (add_logging_to_file,
                                       reset_matchms_logger,
                                       set_matchms_logger_level)
from matchms.SpectrumProcessor import SpectrumProcessor


_masking_functions = ["filter_by_range"]
_score_functions = {key.lower(): f for key, f in mssimilarity.__dict__.items() if callable(f)}
logger = logging.getLogger("matchms")


def create_workflow(yaml_file_name=None,
                    predefined_processing_queries="default",
                    predefined_processing_reference="default",
                    additional_filters_queries=(),
                    additional_filters_references=(),
                    score_computations=(),
                    ):
    # pylint: disable=too-many-arguments
    workflow = OrderedDict()
    queries_processor = initialize_spectrum_processor(predefined_processing_queries, additional_filters_queries)
    workflow["query_filters"] = queries_processor.processing_steps
    reference_processor = initialize_spectrum_processor(predefined_processing_reference, additional_filters_references)
    workflow["reference_filters"] = reference_processor.processing_steps
    workflow["score_computations"] = score_computations
    if yaml_file_name is not None:
        with open(yaml_file_name, 'w', encoding="utf-8") as file:
            file.write("# Matchms pipeline config file \n")
            file.write("# Change and adapt fields where necessary \n")
            file.write("# " + 20 * "=" + " \n")
            ordered_dump(workflow, file)
    return workflow


def initialize_spectrum_processor(predefined_workflow, additional_filters):
    """Initialize spectrum processing workflow."""
    processor = SpectrumProcessor(predefined_workflow)
    for step in additional_filters:
        if isinstance(step, (tuple, list)) and len(step) == 1:
            step = step[0]
        processor.add_filter(step)
    return processor


def load_in_workflow_from_yaml_file(yaml_file):
    with open(yaml_file, 'r', encoding="utf-8") as file:
        workflow = ordered_load(file, yaml.SafeLoader)
    if workflow["reference_filters"] == "processing_queries":
        workflow["reference_filters"] = workflow["query_filters"]
    return workflow


def ordered_load(stream, loader=yaml.SafeLoader, object_pairs_hook=OrderedDict):
    """ Code from https://stackoverflow.com/questions/5121931/in-python-how-can-you-load-yaml-mappings-as-ordereddicts
    """
    class OrderedLoader(loader):
        pass

    def construct_mapping(loader, node):
        loader.flatten_mapping(node)
        return object_pairs_hook(loader.construct_pairs(node))
    OrderedLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        construct_mapping)
    return yaml.load(stream, OrderedLoader)


def ordered_dump(data, stream=None, dumper=yaml.SafeDumper, **kwds):
    class OrderedDumper(dumper):
        pass

    def _dict_representer(dumper, data):
        return dumper.represent_mapping(
            yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
            data.items())
    OrderedDumper.add_representer(OrderedDict, _dict_representer)
    return yaml.dump(data, stream, OrderedDumper, **kwds)


def check_score_computation(score_computations):
    """Check if the score computations seem OK before running.
    Aim is to avoid pipeline crashing after long computation.
    """
    # Check if all score compuation steps exist
    for computation in score_computations:
        if not isinstance(computation, list):
            computation = [computation]
        if isinstance(computation[0], str) and computation[0] in _masking_functions:
            continue
        if isinstance(computation[0], str) and computation[0] in _score_functions:
            continue
        if callable(computation[0]):
            continue
        raise ValueError(f"Unknown score computation: {computation[0]}.")


class Pipeline:
    """Central pipeline class.

    The matchms Pipeline class is meant to make running extensive analysis pipelines
    fast and easy. I can be used in two different ways. First, a pipeline can be defined
    using a config file (a yaml file, best to start from the template provided to define
    your own pipline).

    Once a config file is defined, execution only needs the following code:

    .. code-block:: python

        from matchms import Pipeline

        pipeline = Pipeline("my_config_file.yaml")
        pipeline.run()

    The second way to define a pipeline is via a Python script. The following code is an
    example of how this works:

    .. code-block:: python

        pipeline = Pipeline()
        pipeline.query_files = "spectrums_file.msp"
        pipeline.predefined_processing_queries = "basic"
        pipeline.additional_processing_queries = [
            ["add_parent_mass"],
            ["normalize_intensities"],
            ["select_by_relative_intensity", {"intensity_from": 0.0, "intensity_to": 1.0}],
            ["select_by_mz", {"mz_from": 0, "mz_to": 1000}],
            ["require_minimum_number_of_peaks", {"n_required": 5}]
        ]
        pipeline.score_computations = [["precursormzmatch",  {"tolerance": 120.0}],
                                       ["cosinegreedy", {"tolerance": 1.0}]
                                       ["filter_by_range", {"name": "CosineGreedy_score", "low": 0.3}],
                                       ["modifiedcosine", {"tolerance": 1.0}],
                                       ["filter_by_range", {"name": "ModifiedCosine_score", "low": 0.3}]]

        pipeline.logging_file = "my_pipeline.log"
        pipeline.run()

    To combine this with custom made scores or available matchms-compatible scores
    such as `Spec2Vec` or `MS2DeepScore`, it is also possible to pass objects instead of
    names to the pipeline:

    .. code-block:: python

        from spec2vec import Spec2Vec

        pipeline.score_computations = [["precursormzmatch",  {"tolerance": 120.0}],
                                       [Spec2Vec, {"model": "my_spec2vec_model.model"}],
                                       ["filter_by_range", {"name": "Spec2Vec", "low": 0.3}]]

    """
    def __init__(self, workflow, progress_bar=True, logging_level="WARNING", logging_file=None):
        """
        Parameters
        ----------
        config_file
            Filename of config file (yaml file) to define pipeline. Default is None
            in which case the pipeline should be defined via a Python script.
        progress_bar
            Default is True. Set to False if no progress bar should be displayed.
        """
        self._spectrums_queries = None
        self._spectrums_references = None
        self.is_symmetric = False
        self.scores = None

        self.logging_level = logging_level
        self.logging_file = logging_file
        self.progress_bar = progress_bar
        self.__workflow = workflow
        self.check_workflow()

        self.write_to_logfile("--- Processing pipeline: ---")
        self._initialize_spectrum_processor_queries()
        if self.is_symmetric is False:
            self._initialize_spectrum_processor_references()

    def _initialize_spectrum_processor_queries(self):
        """Initialize spectrum processing workflow for the query spectra."""
        self.processing_queries = initialize_spectrum_processor(
            None,
            self.__workflow["query_filters"]
            )

        self.write_to_logfile(str(self.processing_queries))
        if self.processing_queries.processing_steps != self.__workflow["query_filters"]:
            logger.warning("The order of the filters has been changed compared to the Yaml file.")

    def _initialize_spectrum_processor_references(self):
        """Initialize spectrum processing workflow for the reference spectra."""
        self.processing_references = initialize_spectrum_processor(
            None,
            self.__workflow["reference_filters"]
            )
        self.write_to_logfile(str(self.processing_references))
        self.write_to_logfile(str(self.processing_queries))
        if self.processing_queries.processing_steps != self.__workflow["query_filters"]:
            logger.warning("The order of the filters has been changed compared to the Yaml file.")

    def check_workflow(self):
        """Define Pipeline workflow based on a yaml file (config_file).
        """
        assert isinstance(self.__workflow, OrderedDict), \
            f"Workflow is expectd to be a OrderedDict, instead it was of type {type(self.__workflow)}"
        expected_keys = {"query_filters", "reference_filters", "score_computations"}
        assert set(self.__workflow.keys()) == expected_keys
        check_score_computation(score_computations=self.score_computations)

    def run(self, query_files, reference_files = None):
        """Execute the defined Pipeline workflow.

        This method will execute all steps of the workflow.
        1) Initializing the log file and importing the spectrums
        2) Spectrum processing (using matchms filters)
        3) Score Computations
        """
        self.set_logging()
        self.write_to_logfile("--- Start running matchms pipeline. ---")
        self.write_to_logfile(f"Start time: {str(datetime.now())}")
        self.import_spectrums(query_files, reference_files)

        # Processing
        self.write_to_logfile("--- Processing spectra ---")
        self.write_to_logfile(f"Time: {str(datetime.now())}")
        # Process query spectra
        spectrums, report = self.processing_queries.process_spectrums(
            self._spectrums_queries,
            create_report=True,
            progress_bar=self.progress_bar)
        self._spectrums_queries = spectrums
        self.write_to_logfile(str(report))
        # Process reference spectra (if necessary)
        if self.is_symmetric is False:
            self._spectrums_references, report = self.processing_references.process_spectrums(
                self._spectrums_references,
                create_report=True,
                progress_bar=self.progress_bar)
            self.write_to_logfile(str(report))
        else:
            self._spectrums_references = self._spectrums_queries

        # Score computation and masking
        self.write_to_logfile("--- Computing scores ---")
        for i, computation in enumerate(self.score_computations):
            self.write_to_logfile(f"Time: {str(datetime.now())}")
            if not isinstance(computation, list):
                computation = [computation]
            if isinstance(computation[0], str) and computation[0] in _masking_functions:
                self.write_to_logfile(f"-- Score masking: {computation} --")
                self._apply_score_masking(computation)
            else:
                self.write_to_logfile(f"-- Score computation: {computation} --")
                self._apply_similarity_measure(computation, i)
        self.write_to_logfile(f"--- Pipeline run finised ({str(datetime.now())}) ---")

    def _apply_score_masking(self, computation):
        """Apply filter to remove scores which are out of the set range.
        """
        if len(computation) == 1:
            name = self.scores.score_names[-1]
            self.scores.filter_by_range(name=name)
        elif "name" not in computation[1]:
            name = self.scores.scores.score_names[-1]
            self.scores.filter_by_range(name=name, **computation[1])
        else:
            self.scores.filter_by_range(**computation[1])

    def _apply_similarity_measure(self, computation, i):
        """Run score computations for all listed methods and on all loaded and processed spectra.
        """
        def get_similarity_measure(computation):
            if isinstance(computation[0], str):
                if len(computation) > 1:
                    return _score_functions[computation[0]](**computation[1])
                return _score_functions[computation[0]]()
            if callable(computation[0]):
                if len(computation) > 1:
                    return computation[0](**computation[1])
                return computation[0]()
            raise TypeError("Unknown similarity measure.")
        similarity_measure = get_similarity_measure(computation)
        # If this is the first score computation:
        if i == 0:
            self.scores = calculate_scores(self._spectrums_references,
                                           self._spectrums_queries,
                                           similarity_measure,
                                           array_type="sparse",
                                           is_symmetric=self.is_symmetric)
        else:
            new_scores = similarity_measure.sparse_array(references=self._spectrums_references,
                                                         queries=self._spectrums_queries,
                                                         idx_row=self.scores.scores.row,
                                                         idx_col=self.scores.scores.col,
                                                         is_symmetric=self.is_symmetric)
            self.scores.scores.add_sparse_data(self.scores.scores.row,
                                               self.scores.scores.col,
                                               new_scores,
                                               similarity_measure.__class__.__name__)

    def set_logging(self):
        """Set the matchms logger to write messages to file (if defined).
        """
        reset_matchms_logger()
        set_matchms_logger_level(self.logging_level)
        if self.logging_file is not None:
            add_logging_to_file(self.logging_file,
                                loglevel=self.logging_level,
                                remove_stream_handlers=True)
        else:
            logger.warning("No logging file was defined."
                           "Logging messages will not be written to file.")

    def write_to_logfile(self, line):
        """Write message to log file.
        """
        if self.logging_file is not None:
            with open(self.logging_file, "a", encoding="utf-8") as f:
                f.write(line + '\n')

    def import_spectrums(self, query_files, reference_files=None):
        """Import spectra from file(s).

        Parameters
        ----------
        query_files
            List of files, or single filename, containing the query spectra.
        reference_files
            List of files, or single filename, containing the reference spectra.
            If set to None (default) then all query spectra will be compared to each other.
        """
        def check_files_exist(filenames):
            assert filenames is not None
            if isinstance(filenames, str):
                filenames = [filenames]
            for filename in filenames:
                assert os.path.exists(filename), f"File {filename} not found."

        # Check if all files exist
        check_files_exist(query_files)
        if reference_files is not None:
            check_files_exist(reference_files)

        if isinstance(query_files, str):
            query_files = [query_files]
        if isinstance(reference_files, str):
            reference_files = [reference_files]
        self.write_to_logfile("--- Importing data ---")

        # import query spectra
        spectrums_queries = []
        for query_file in query_files:
            spectrums_queries += list(load_spectra(query_file))
        self._spectrums_queries = spectrums_queries
        self.write_to_logfile(f"Loaded query spectra from {query_files}")
        self.write_to_logfile(f"Loaded {len(self._spectrums_queries)} query spectra")

        # import reference spectra
        if reference_files is None:
            self.is_symmetric = True
            self._spectrums_references = self._spectrums_queries
            self.write_to_logfile("Reference spectra are equal to the query spectra (is_symmetric = True)")
        else:
            spectrums_references = []
            for reference_file in reference_files:
                spectrums_references += list(load_spectra(reference_file))
            self._spectrums_references = spectrums_references
            self.write_to_logfile(f"Loaded reference spectra from {reference_files}")
            self.write_to_logfile(f"Loaded {len(self._spectrums_references)} reference spectra")

    # Getter & Setters
    @property
    def score_computations(self):
        return self.__workflow.get("score_computations")

    @score_computations.setter
    def score_computations(self, computations):
        self.__workflow["score_computations"] = computations
        check_score_computation(score_computations=self.score_computations)

    @property
    def query_filters(self):
        return self.__workflow.get("query_filters")

    @query_filters.setter
    def query_filters(self, filters):
        self.__workflow["query_filters"] = filters
        self._initialize_spectrum_processor_queries()

    @property
    def reference_filters(self):
        return self.__workflow.get("reference_filters")

    @reference_filters.setter
    def reference_filters(self, filters):
        self.__workflow["refernece_filters"] = filters
        self._initialize_spectrum_processor_references()

    @property
    def spectrums_queries(self):
        return self._spectrums_queries

    @property
    def spectrums_references(self):
        return self._spectrums_references
