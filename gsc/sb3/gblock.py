import json
from typing import Any, Sized, Union

from lark import Token
from lib import JSON, tripletwise

from .gblockfactory import gPrototype

gInputType = Union[str, "gBlock", "gStack", "gVariable", "gList"]
gFieldType = Union[str, "gVariable", "gList"]
gBlockListType = dict[str, dict[str, JSON]]


def proccode(name: str, inputs: Sized):
    return name + " " + " ".join(["%s"] * len(inputs))


class gVariable(str):
    ...


class gList(str):
    ...


class gBlock:
    def __init__(
        self, opcode: str, inputs: dict[str, gInputType], fields: dict[str, gFieldType]
    ):
        self.opcode = opcode
        self.inputs = inputs
        self.fields = fields
        self.id = str(id(self))

    @classmethod
    def from_prototype(cls, prototype: gPrototype, arguments: list[gInputType]):
        return cls(prototype.opcode, dict(zip(prototype.arguments, arguments)), {})

    def __rich_repr__(self) -> Any:
        yield "opcode", self.opcode
        yield "inputs", self.inputs
        yield "fields", self.fields

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.opcode}, {self.inputs}, {self.fields})"

    def serialize_input(self, blocks: gBlockListType, value: gInputType) -> JSON:
        if type(value) is str:
            return [1, [10, value]]
        elif type(value) is gVariable:
            return [2, [12, value, value]]
        elif type(value) is gList:
            ...
        elif isinstance(value, gStack):
            return [2, value[0].id]
        elif isinstance(value, gBlock):
            value.serialize(blocks, None, self.id)
            return [2, value.id]
        raise ValueError(self, value)

    def serialize_field(self, blocks: gBlockListType, value: gFieldType) -> JSON:
        if isinstance(value, str):
            return [value]
        raise ValueError(self, value)

    def serialize_inputs(self, blocks: gBlockListType):
        return {
            name: self.serialize_input(blocks, value)
            for name, value in self.inputs.items()
        }

    def serialize_fields(self, blocks: gBlockListType):
        return {
            name: self.serialize_field(blocks, value)
            for name, value in self.fields.items()
        }

    def serialize(self, blocks: gBlockListType, next: str | None, parent: str | None):
        blocks[self.id] = {
            "opcode": self.opcode,
            "next": next,
            "parent": parent,
            "inputs": self.serialize_inputs(blocks),
            "fields": self.serialize_fields(blocks),
            "topLevel": isinstance(self, gHatBlock),
        }


class gStack(list[gBlock]):
    def serialize(self, blocks: gBlockListType, parent: str):
        for prev, this, next in tripletwise(self):
            this.serialize(blocks, next and next.id, prev.id if prev else parent)


class gHatBlock(gBlock):
    def __init__(
        self,
        opcode: str,
        inputs: dict[str, gInputType],
        fields: dict[str, gFieldType],
        stack: gStack,
    ):
        super().__init__(opcode, inputs, fields)
        self.stack = stack

    @classmethod
    def from_prototype(
        cls, prototype: gPrototype, arguments: list[gInputType], stack: gStack
    ):
        return cls(
            prototype.opcode, dict(zip(prototype.arguments, arguments)), {}, stack
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.opcode}, {self.inputs}, {self.fields}, {self.stack})"

    def serialize(self, blocks: gBlockListType, next: str | None, parent: str | None):
        super().serialize(
            blocks, self.stack[0].id if len(self.stack) > 0 else None, parent
        )
        self.stack.serialize(blocks, self.id)


class gArgument(gBlock):
    def __init__(self, name: str):
        super().__init__("argument_reporter_string_number", {}, {"VALUE": name})


class gProcCall(gBlock):
    def __init__(self, name: str, inputs: dict[str, gInputType], warp: bool):
        super().__init__("procedures_call", inputs, {})
        self.name = name
        self.warp = warp

    def serialize(self, blocks: gBlockListType, next: str | None, parent: str | None):
        super().serialize(blocks, next, parent)
        blocks[self.id]["mutation"] = {
            "tagName": "mutation",
            "children": [],
            "proccode": proccode(self.name, self.inputs),
            "argumentids": json.dumps(list(self.inputs.keys())),
            "warp": self.warp,
        }


class gProcProto(gBlock):
    def __init__(self, name: str, arguments: list[Token], warp: bool):
        super().__init__(
            "procedures_prototype",
            {argument: gArgument(argument) for argument in arguments},
            {},
        )
        self.name = name
        self.warp = warp

    def serialize(self, blocks: gBlockListType, next: str | None, parent: str | None):
        super().serialize(blocks, next, parent)
        argumentids = json.dumps(list(self.inputs.keys()))
        blocks[self.id]["mutation"] = {
            "tagName": "mutation",
            "children": [],
            "proccode": proccode(self.name, self.inputs),
            "argumentids": argumentids,
            "argumentnames": argumentids,
            "argumentdefaults": json.dumps(["0"] * len(self.inputs)),
            "warp": json.dumps(self.warp),
        }


class gProcDef(gHatBlock):
    def __init__(
        self,
        name: str,
        arguments: list[Token],
        warp: bool,
        stack: gStack,
    ):
        super().__init__(
            "procedures_definition",
            {"custom_block": gProcProto(name, arguments, warp)},
            {},
            stack,
        )
