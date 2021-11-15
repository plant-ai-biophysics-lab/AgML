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

import copy


class AgMLSerializable(object):
    """Base class for all AgML serializable objects.

    Most objects in AgML inherit from this class, and are thus
    serializable into a JSON or binary (such as pickle) framework,
    allowing objects to be easily accessed, adjusted, and copied.

    More specifically, subclasses of this will have an automatically
    defined `__getstate__` and `__setstate__` method which consists
    of a dictionary with the necessary class attributes. In addition,
    it will have a `__copy__` and `__deepcopy__` method which have
    the same behavior (the class is always deep copied).

    Subclasses only need to define a `serializable` property with a
    frozen set of strings containing the attributes that are to be
    serialized. The expectation is that the strings in the set will
    all be the name of attributes minus a leading underscore.

    In turn, objects can be used with a JSON serialization format,
    the pickle serialization format, or copied as desired.
    """
    serializable: "frozenset"

    def __getstate__(self):
        state = {}
        for param in self.serializable:
            try:
                state[param] = getattr(self, f'_{param}')
            except AttributeError:
                raise AttributeError(
                    f"Encountered error while attempting to "
                    f"serialize a {self.__class__}: the "
                    f"attribute '_{param}' does not exist.")
        return state

    def __setstate__(self, state):
        for field in state.keys():
            setattr(self, f'_{field}', state[field])

    def __copy__(self):
        params = self.__getstate__()
        cls = super(AgMLSerializable, self).__new__(self.__class__)
        cls.__setstate__(copy.deepcopy(params))
        return cls

    def __deepcopy__(self, memo = None):
        return self.__copy__()




