# Copyright 2021 UC Davis Plant AI and Biophysics Lab
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import torch.multiprocessing

from pytorch_lightning import Trainer
from pytorch_lightning.loggers import WandbLogger

import agml
from agml.models.training_resources.detection_data import (
    build_loader, TransformApplier, EfficientDetDataModule
)
from agml.models.training_resources.detection_modeling import (
    DetectionTrainingModel
)
from agml.models.training_resources.tools import gpus


class DetectionExperiment(object):
    """Runs an object detection experiment with the input arguments."""

    def __init__(self, parameters):
        self._initialize_experiment(parameters)

    def _initialize_experiment(self, params: dict):
        # Get the datasets for which the model is being trained.
        datasets = params['dataset']
        for dataset in datasets:
            if dataset not in agml.data.public_data_sources(
                    ml_task = 'object_detection'):
                raise ValueError(
                    f"The provided dataset '{dataset}' is not a valid "
                    f"object detection dataset in AgML. Try another one.")

        # Construct the object detection loader.
        self._loader = build_loader(dataset = datasets,
                                    batch_size = params.get('batch_size', 4))

        # If the user wants to generalize detections, generalize.
        if params.get('generalize_detections', False):
            self._loader.generalize_class_detections()

        # Parse the loader for a loader experiment.
        self._parse_loader()

        # Parse augmentations for an augmentations experiment.
        augmentations = self._parse_augmentations(
            params.get('augmentations', None))

        # Construct the data module.
        self._data_module = EfficientDetDataModule(
            loader = self._loader.copy(),
            augmentation = augmentations,
            num_workers = params.get('num_workers', 8))

        # Construct the checkpoint and log directory.
        experiment_name = params.get('name', None)
        experiment_dir_default = params.get('experiment_dir', None)
        if experiment_dir_default is None:
            if experiment_name is None:
                raise ValueError("Expected either the experiment name or save directory.")
            if os.path.exists('/data2'):
                experiment_dir = os.path.join(
                    '/data2/amnjoshi/experiments', experiment_name)
            else:
                experiment_dir = os.path.join('.', experiment_name)
        else:
            experiment_dir = experiment_dir_default
        os.makedirs(experiment_dir, exist_ok = True)
        self._experiment_dir = experiment_dir
        if experiment_name is None:
            experiment_name = os.path.basename(experiment_dir)

        # Initialize the model.
        num_classes = params.get('num_classes', None)
        if num_classes is None:
            num_classes = self._loader.num_classes
        self._model = DetectionTrainingModel(
            num_classes = num_classes,
            pretrained_weights = params.get('pretrained_weights', False),
            confidence_threshold = params.get('confidence_threshold', 0.3),
            learning_rate = params.get('learning_rate', 0.0002),
            wbf_iou_threshold = params.get('wbf_iou_threshold', 0.44))
        self._model.load_state_dict(torch.load('/data2/amnjoshi/final/detection_checkpoints/grape_detection_californiaday/final_model.pth'))

        # Build the loggers.
        # loggers = [
        #     WandbLogger(name = experiment_name,
        #                 save_dir = experiment_dir)
        # ]

        # Construct the `Trainer` with the model.
        self._trainer = Trainer(gpus = gpus(None),
                                max_epochs = params.get('epochs', 25))

    def _parse_loader(self):
        """Can be overridden by a subclass for data experiments."""
        return self._loader

    def _parse_augmentations(self, augmentations): # noqa
        """Can be overridden by a subclass to run an augmentation experiment."""
        return TransformApplier(augmentations)

    def train(self):
        self._trainer.fit(self._model,
                          self._data_module)


if __name__ == '__main__':
    parameters = dict(
        epochs = 10,
        name = 'thingy',
        dataset = ['grape_detection_californiaday'],
        num_workers = 0,
        batch_size = 2,
    )
    DetectionExperiment(parameters).train()


