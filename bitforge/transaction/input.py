from __future__ import unicode_literals
import collections

from bitforge.encoding import *
from bitforge.errors import *
from bitforge.tools import Buffer
from bitforge.signature import SIGHASH_ALL
from bitforge.script import Script, PayToPubkeyIn, PayToScriptIn, RedeemMultisig, PayToPubkeyOut


FINAL_SEQ_NUMBER = 0xFFFFFFFF


BaseInput = collections.namedtuple('Input',
    ['tx_id', 'txo_index', 'script', 'seq_number']
)


class Input(BaseInput):

    class Error(BitforgeError):
        pass

    class UnknownSignatureMethod(Error):
        "This abstract Input doesn't know how to sign itself. You should use an Input subclass, such as AddressInput"

    class InvalidSignatureCount(Error):
        "This Input requires {required} keys to sign, but {provided} were provided"

        def prepare(self, required_keys, provided_keys):
            self.required = required_keys
            self.provided = provided_keys


    def __new__(cls, tx_id, txo_index, script, seq_number = FINAL_SEQ_NUMBER):
        # TODO validation
        return super(Input, cls).__new__(cls, tx_id, txo_index, script, seq_number)

    @classmethod
    def create(cls, tx_id, txo_index, script, seq_number = FINAL_SEQ_NUMBER):
        script = Script.create(script.instructions) # classified copy
        args = (tx_id, txo_index, script, seq_number)

        if isinstance(script, PayToPubkeyIn):
            return AddressInput(*args)

        elif isinstance(script, PayToScriptIn):
            return ScriptInput(*args)

        elif isinstance(script, OpReturnOut):
            return DataOutput(*args)

        else:
            return Output(amount, script)

    def to_bytes(self):
        buffer = Buffer()
        script = self.script.to_bytes()

        # Reverse transaction ID (double SHA256 hex of previous tx) (32 bytes):
        buffer.write(reversed(decode_hex(self.tx_id)))

        # Previous tx output index, as little-endian uint32 (4 bytes):
        buffer.write(encode_int(self.txo_index, length = 4, big_endian = False))

        # Script length, as variable-length integer (1-9 bytes):
        buffer.write(encode_varint(len(script)))

        # Script body (? bytes):
        buffer.write(script)

        # Sequence number, as little-endian uint32 (4 bytes):
        buffer.write(encode_int(self.seq_number, length = 4, big_endian = False))

        return str(buffer)

    def to_hex(self):
        return encode_hex(self.to_bytes()).decode('utf-8')

    def replace_script(self, script):
        return Input(self.tx_id, self.txo_index, script, self.seq_number)

    def remove_script(self):
        return self.replace_script(Script())

    def sign(self, privkeys, payload, sigtype = SIGHASH_ALL):
        # Signing an Input requires knowledge of two things:
        #
        # 1. The placeholder Script that will be used in place of the signed one,
        # to construct the actual signature (it can't sign itself)
        #
        # 2. The method with which to construct the final, signed Script
        #
        # By the time this method is invoked, the placeholder script (1) should
        # already be waiting in our `script` property, but (2) we can't know
        # about. See Input subclasses.
        raise Input.UnknownSignatureMethod()

    @classmethod
    def from_hex(cls, string):
        return cls.from_bytes(decode_hex(string))

    @classmethod
    def from_bytes(cls, bytes):
        return cls.from_buffer(Buffer(bytes))

    @classmethod
    def from_buffer(cls, buffer):
        # Inverse operation of Input.to_bytes(), check that out.
        tx_id     = encode_hex(buffer.read(32)[::-1]) # reversed
        txo_index = decode_int(buffer.read(4), big_endian = False)

        script_len = buffer.read_varint()
        script     = Script.from_bytes(buffer.read(script_len))

        seq_number = decode_int(buffer.read(4), big_endian = False)

        return cls(tx_id, txo_index, script, seq_number)


class AddressInput(Input):

    @classmethod
    def create(cls, tx_id, txo_index, address, seq_number = FINAL_SEQ_NUMBER):
        # The placeholder Script for an AddressInput (Pay-to-Pubkey, in raw
        # Bitcoin terms) is a copy of the UTXO Script from the previous
        # transaction. Assuming that Output had a standard Pay-to-Pubkey Script,
        # we don't need to actually fetch the data.
        placeholder_script = PayToPubkeyOut.create(address)

        return cls(tx_id, txo_index, placeholder_script, seq_number)

    def sign(self, privkeys, payload, sigtype = SIGHASH_ALL):
        if len(privkeys) != 1:
            raise AddressInput.InvalidSignatureCount(1, len(privkeys))

        signed_script = PayToPubkeyIn.create(
            pubkey    = privkeys[0].to_public_key(),
            signature = privkeys[0].sign(payload) + chr(sigtype)
        )

        return self.replace_script(signed_script)

    def can_sign(self, privkeys):
        return (
            len(privkeys) == 1 and
            privkeys[0].to_address().phash == self.script.get_address_hash()
        )


class ScriptInput(Input):

    @classmethod
    def create(cls, tx_id, txo_index, script, seq_number = FINAL_SEQ_NUMBER):
        # The placeholder Script for a ScriptInput (Pay-to-Script, in raw
        # Bitcoin terms) is the embedded (redeeming) Script itself.

        return cls(tx_id, txo_index, script, seq_number)

    def sign(self, privkeys, payload, sigtype = SIGHASH_ALL):
        # Signing a ScriptInput requires embedding the redeem Script (already
        # set as placeholder in our `script` property by the time this method
        # is invoked) in a standard Pay-to-Script Script.
        signed_script = PayToScriptIn.create(
            script     = self.script,
            signatures = [ pk.sign(payload) + chr(sigtype) for pk in privkeys ]
        )

        return self.replace_script(signed_script)


class MultisigInput(ScriptInput):

    @classmethod
    def create(cls, tx_id, txo_index, pubkeys, min_signatures, seq_number = FINAL_SEQ_NUMBER):
        # There is nothing magical about a MultisigInput. All we need to do
        # is construct the placeholder Script for the ScriptInput automatically,
        # since we know the form it will take.
        placeholder_script = RedeemMultisig.create(pubkeys, min_signatures)

        return cls(tx_id, txo_index, placeholder_script, seq_number)

    def can_sign(self, privkeys):
        if len(privkeys) != self.script.get_min_signatures():
            return False

        expected_pubkeys = self.script.get_public_keys()

        for privkey in privkeys:
            if privkey.to_public_key() not in expected_pubkeys:
                return False

        return True
