# Copyright 2019 PyI40AAS Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
# specific language governing permissions and limitations under the License.
"""
This module generates identifiers.

Generate [identifier]:  -> Try:
Abstract                -> AbstractIdentifierGenerator
UUID                    -> UUIDGenerator
IRI                     -> NamespaceIRIGenerator
"""

import abc
import re
import uuid
from typing import Optional, Dict, Union, Set

from .. import model


class AbstractIdentifierGenerator(metaclass=abc.ABCMeta):
    """
    Abstract base class for identifier generators that generate identifiers based on an internal schema and an
    (optional) proposal.

    Different Implementations of IdentifierGenerators may generate differently formed ids, e.g. URNs, HTTP-scheme IRIs,
    IRDIs, etc. Some of them may use a given private namespace and create ids within this namespace, others may just
    use long random numbers to ensure uniqueness.
    """
    @abc.abstractmethod
    def generate_id(self, proposal: Optional[str] = None) -> model.Identifier:
        """
        Generate a new Identifier for an Identifiable object.

        :param proposal: An optional string for a proposed suffix of the Identification (e.g. the last path part or
                         fragment of an IRI). It may be ignored by some implementations of or be changed if the
                         resulting id is already existing.
        """
        pass


class UUIDGenerator(AbstractIdentifierGenerator):
    """
    An IdentifierGenerator, that generates URNs of version 1 UUIDs according to RFC 4122.
    """
    def __init__(self):
        super().__init__()
        self._sequence = 0

    def generate_id(self, proposal: Optional[str] = None) -> model.Identifier:
        uuid_ = uuid.uuid1(clock_seq=self._sequence)
        self._sequence += 1
        return model.Identifier("urn:uuid:{}".format(uuid_), model.IdentifierType.IRI)


class NamespaceIRIGenerator(AbstractIdentifierGenerator):
    """
    An IdentifierGenerator, that generates IRIs in a given namespace, checking uniqueness against a Registry.

    Identifiers are generated by concatenating a fixed namespace with the proposed suffix. To verify uniqueness, the
    existence of the identification is checked by querying the given Registry. If a collision is detected, a number
    is prepended
    """
    def __init__(self, namespace: str, provider: model.AbstractObjectProvider):
        """
        Create a new NamespaceIRIGenerator
        :param namespace: The IRI Namespace to generate Identifications in. It must be a valid IRI (starting with a
                          scheme) and end on either #, /, or = to form a reasonable namespace.
        :param provider: An AbstractObjectProvider to check existence of Identifiers
        """
        super().__init__()
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9+\-\.]*:.*[#/=]$', namespace):
            raise ValueError("Namespace must be a valid IRI, ending with #, / or =")
        self.provider = provider
        self._namespace = namespace
        self._counter_cache: Dict[str, int] = {}

    @property
    def namespace(self):
        return self._namespace

    def generate_id(self, proposal: Optional[str] = None) -> model.Identifier:
        if proposal is None:
            proposal = ""
        proposal = _quote_iri_segment(proposal)
        counter: int = self._counter_cache.get(proposal, 0)
        while True:
            if counter or not proposal:
                iri = "{}{}{}{:04d}".format(self._namespace, proposal, "_" if proposal else "", counter)
            else:
                iri = "{}{}".format(self._namespace, proposal)
            # Try to find iri in provider. If it does not exist (KeyError), we found a unique one to return
            try:
                self.provider.get_identifiable(model.Identifier(iri, model.IdentifierType.IRI))
            except KeyError:
                self._counter_cache[proposal] = counter
                return model.Identifier(iri, model.IdentifierType.IRI)
            counter += 1


# Reserved IRI characters according to https://tools.ietf.org/html/rfc3987#section-2.2
# minus '/', '?', '=', '&', '#', which can be used in a path, querystring and fragment
# plus unallowed characters (see) https://stackoverflow.com/a/36667242/10315508
_iri_segment_quote_table_tmpl: Dict[Union[str, int], Optional[str]] = {
    c: '%{:02X}'.format(c.encode()[0])
    for c in [
        ':', '[', ']', '@',  # '/', '?', '#',
        '!', '$', '\'', '(', ')', '*', '+', ',', ';',  # '=', '&',
        ' ', '"', '<', '>', '\\', '^', '`', '{', '|', '}',
    ]}
# Remove ASCII control characters
_iri_segment_quote_table_tmpl.update({
    i: None
    for i in range(0, 0x1f)})
_iri_segment_quote_table_tmpl[0x7f] = None
_iri_segment_quote_table: Dict[int, Optional[str]] = str.maketrans(_iri_segment_quote_table_tmpl)


def _quote_iri_segment(segment: str) -> str:
    return segment.translate(_iri_segment_quote_table)
