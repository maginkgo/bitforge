from pytest import raises, fixture, fail
import bitforge.networks
from bitforge.privkey import PrivateKey
from bitforge.pubkey import PublicKey
from bitforge.script import Interpreter, Script
from bitforge.encoding import encode_int, decode_hex, encode_script_number
from bitforge.script.opcode import *


class TestInterpreter:

    def test_init_interpreter(self):
        interpreter = Interpreter()

        assert len(interpreter.stack) == 0
        assert len(interpreter.altstack) == 0
        assert len(interpreter.vf_exec) == 0
        assert interpreter.pc == 0
        assert interpreter.pbegincodehash == 0
        assert interpreter.nop_count == 0
        assert interpreter.errstr == ''
        assert interpreter.flags == 0

    def test_cast_to_bool(self):
        assert Interpreter.cast_to_bool(encode_script_number(0)) is False
        assert Interpreter.cast_to_bool(decode_hex('008A')) is False  # Negative 0
        assert Interpreter.cast_to_bool(encode_script_number(1)) is True
        assert Interpreter.cast_to_bool(encode_script_number(-1)) is True

    def test_verify_trivial_scripts(self):
        interpreter = Interpreter()

        verified = interpreter.verify(Script.compile([OP_1]), Script.compile([OP_1]))
        assert verified is True

        verified = interpreter.verify(Script.compile([OP_1]), Script.compile([OP_0]))
        assert verified is False

        verified = interpreter.verify(Script.compile([OP_0]), Script.compile([OP_1]))
        assert verified is True

        verified = interpreter.verify(Script.compile([OP_CODESEPARATOR]), Script.compile([OP_1]))
        assert verified is True

        verified = interpreter.verify(Script(), Script.compile([OP_DEPTH, OP_0, OP_EQUAL]))
        assert verified is True

        # verified = interpreter.verify(Script.from_string('9 0x000000000000000010'), Script())
        # assert verified is True

        verified = interpreter.verify(Script.compile([OP_1]), Script.compile([OP_15, OP_ADD, OP_16, OP_EQUAL]))
        assert verified is True

        verified = interpreter.verify(Script.compile([OP_0]), Script.compile([OP_IF, OP_VERIFY, OP_ELSE, OP_1, OP_ENDIF]))
        assert verified is True



    # def test_from_hex_errors(self):
    #     with raises(PublicKey.InvalidHex): PublicKey.from_hex('a')
    #     with raises(PublicKey.InvalidHex): PublicKey.from_hex('a@')

    # def test_to_hex_uncompressed(self):
    #     string = '04b805174bd496b275e711d5a9f1bcbaa4bba1a77176dbdb5fdd8b769da62a36a9c3dfa7c8ccb509f9a66efd6d8d1db6b25aa7c100476154b6303d76c28eda099b'
    #     assert PublicKey.from_hex(string).to_hex() == string
