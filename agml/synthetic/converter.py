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
import sys
import glob
import json
import shutil
from typing import List
from dataclasses import dataclass
from datetime import datetime as dt

import numpy as np

from agml.utils.io import recursive_dirname, get_dir_list
from agml.utils.logging import tqdm


@dataclass
class DataFormatConverterMetadata:
    path: str
    name: str
    image_size: str
    annotation_type: str
    labels: List[str]
    generation_date: str


class HeliosDataFormatConverter(object):
    """Converts the annotation and organization of a Helios dataset."""

    def __init__(self, dataset):
        # Locate the dataset and parse its metadata.
        self._meta = self.parse_metadata(dataset)

    def parse_metadata(self, dataset):
        """Parse the metadata of the dataset for use in conversion."""
        # Locate the dataset and get its actual name.
        output_dir = self._locate_dataset(dataset)
        name = os.path.basename(output_dir)
        meta = {'path': output_dir, 'name': name}
        meta_dir = os.path.join(output_dir, '.metadata')

        # Get the annotation type and the labels from the configuration file.
        with open(os.path.join(meta_dir, f'config_{name}.txt'), 'r') as f:
            contents = [i.replace("\n", "") for i in f.readlines()]
            meta['annotation_type'] = contents[1]
            meta['labels'] = contents[3].split(' ')

        # Get the image resolution and date created from the metadata file.
        with open(os.path.join(meta_dir, 'meta.json'), 'r') as f:
            contents = json.load(f)
            meta['image_size'] = contents['image_size']
            meta['generation_date'] = contents['generation_date']

        # Return the options.
        return DataFormatConverterMetadata(**meta)

    @staticmethod
    def _locate_dataset(name):
        if os.path.exists(name) and os.path.isdir(name):
            return name
        syn_path = os.path.join(os.path.expanduser('~/.agml/synthetic'), name)
        if os.path.exists(syn_path) and os.path.isdir(syn_path):
            return syn_path
        raise NotADirectoryError(
            f"The provided dataset `{name}` is not a path, "
            f"and if it were to be the name of a dataset, "
            f"then {syn_path} does not exist either.")

    def convert(self):
        """Runs the data format conversion for the input Helios dataset.

        This method runs the actual conversion of the dataset format, as specific
        for the annotation type: object detection vs. semantic segmentation. The
        newly organized dataset is written to its existing location, and if the
        conversion is successful, then the original organization is cleared out.
        """
        if self._meta.annotation_type == 'object_detection':
            try:
                self._convert_object_detection_dataset()
            except Exception as e:
                self._cleanup_failed_object_detection_conversion()
                raise e
            else:
                self._remove_existing_image_dirs()

    def _convert_object_detection_dataset(self):
        """Converts the format of an object detection dataset to COCO JSON."""
        # Get all of the images in the dataset.
        jpeg_images = glob.glob(
            os.path.join(self._meta.path, "image*/**/*.jpeg"), recursive = True)

        # For each of the images, get their corresponding annotations.
        image_annotation_map = {}
        for image in jpeg_images:
            image_dir = os.path.dirname(image)
            image_annotation_map[image] = \
                self._convert_text_files_to_object_annotations(image_dir)

        # Create a virtual output directory structure and the new filenames.
        self._create_output_directory_structure()

        # Move all of the images.
        image_new_map = self._map_and_move_images(list(image_annotation_map.keys()))

        # Generate the image COCO JSON contents.
        image_coco, image_id_map = [], {}
        for indx, image in enumerate(image_annotation_map.keys()):
            image_id_map[image] = indx + 1
            fpath = os.path.basename(image_new_map[image])
            image_coco.append({
                'file_name': fpath, 'height': self._meta.image_size[0],
                'width': self._meta.image_size[1], 'id': indx + 1})

        # Generate the annotation COCO JSON contents.
        annotation_coco = []
        for indx, (image, annotation) in enumerate(image_annotation_map.items()):
            image_box_tracker = 1
            for label, bboxes in annotation.items():
                for box in bboxes:
                    annotation_coco.append({
                        'bbox': box.tolist(), 'area': int(box[2] * box[3]),
                        'category_id': label, 'image_id': image_id_map[image],
                        'id': image_box_tracker, 'iscrowd': 0, 'ignore': 0,
                        'segmentation': []})
                    image_box_tracker += 1

        # Create the category mapping and the meta information.
        category_coco = [
            {'name': name, 'supercategory': 'none', 'id': i}
            for i, name in enumerate(self._meta.labels)]
        info_coco = {
            'description': f"{self._meta.name}: Helios-generated dataset",
            'url': 'None', 'version': '1.0', 'year': dt.now().year,
            'contributor': 'None', 'date_created': self._meta.generation_date}

        # Save the JSON file with the annotations.
        with open(os.path.join(self._meta.path, 'annotations.json'), 'w') as f:
            json.dump({
                'images': image_coco, 'annotations': annotation_coco,
                'categories': category_coco, 'info': info_coco}, f, indent = 4)

    def _convert_text_files_to_object_annotations(self, image_dir):
        """Converts text file annotations to COCO JSON object annotations."""
        height, width = self._meta.image_size
        txt_fmt = os.path.join(image_dir, 'rectangular_labels_{0}.txt')

        # Read each of the files corresponding to the given labels.
        bboxes = {}
        for indx, label in enumerate(self._meta.labels):
            # Get the path to the specific text file and check for its existence.
            path = txt_fmt.format(label)
            if not os.path.exists(path):
                err = FileNotFoundError(
                    f"The annotation file {path} for the label `{label}` "
                    f"for the image at {image_dir} does not exist. ")
                if label == 'fruits':
                    path = txt_fmt.format('clusters')
                    if not os.path.exists(path):
                        raise err
                else:
                    raise err

            # Read the text file and get all of the lines in float format.
            with open(path, 'r') as f:
                annotations = np.array(
                    [line.replace('\n', '').strip().split(' ') for line in f.readlines()])
                annotations = annotations[:, 1:].astype(np.float32)

            # Convert the bounding boxes to COCO JSON format.
            # (data[l][1])-0.5*data[l][3],  (img.shape[0] - data[l][2])- 0.5* data[l][4]), data[l][3], data[l][4]
            x_c, y_c, w, h = np.rollaxis(annotations, 1)
            x_min = (x_c - w / 2) * width
            y_min = ((1 - y_c) - h / 2) * height
            w = w * width
            h = h * height
            coords = np.dstack([x_min, y_min, w, h])[0].astype(np.int32)

            # Update the bounding box dictionary.
            bboxes[indx + 1] = coords

        # Return the bounding box dictionary.
        return bboxes

    def _create_output_directory_structure(self):
        """Builds the output directory structure for the dataset."""
        if self._meta.annotation_type == 'object_detection':
            data_dir = self._meta.path
            image_dir = os.path.join(data_dir, 'images')
            os.makedirs(image_dir, exist_ok = True)

    def _map_and_move_images(self, images):
        """Maps all of the images to a new ID and moves them."""
        image_new_map = {}
        output_dir = os.path.join(self._meta.path, 'images')
        for image in tqdm(images, file = sys.stdout, desc = "Moving Images"):
            image_num = os.path.basename(recursive_dirname(image, 2))
            view_num = os.path.basename(recursive_dirname(image, 1))
            image_name = f"{image_num}-{view_num}.jpeg"
            shutil.copyfile(image, os.path.join(output_dir, image_name))
            image_new_map[image] = os.path.join(output_dir, image_name)
        return image_new_map

    def _cleanup_failed_object_detection_conversion(self):
        """Cleans up the remnants of a failed conversion for object detection."""
        if os.path.exists(os.path.join(self._meta.path, 'annotations.json')):
            os.remove(os.path.join(self._meta.path, 'annotations.json'))
        if os.path.exists(os.path.join(self._meta.path, 'images')):
            shutil.rmtree(os.path.join(self._meta.path, 'images'))

    def _remove_existing_image_dirs(self):
        """Removes the original image directories after a successful conversion."""
        image_dirs = [
            dir_ for dir_ in get_dir_list(self._meta.path) if dir_[-1].isnumeric()]
        for image_dir in image_dirs:
            shutil.rmtree(os.path.join(self._meta.path, image_dir))






