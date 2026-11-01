# Upstream model attribution

The Cytellect NCL candidate is a fine-tune of the Cellpose-SAM `cpsam_v2`
checkpoint distributed by MouseLand.

- Upstream repository: https://huggingface.co/mouseland/cellpose-sam
- Upstream revision: `7c61431b5fbb078f3296754bd15d9f51b320f837`
- Upstream checkpoint SHA256: `0f1cc3f7ecdd8a037a57c6c48d9d8921391be4cbce3fa9f13c3e3a2e1253c667`
- That revision's model card declares `bsd-3-clause`:
  https://huggingface.co/mouseland/cellpose-sam/blob/7c61431b5fbb078f3296754bd15d9f51b320f837/README.md
- The upstream copyright, conditions and disclaimer are reproduced in
  `LICENSE.cellpose`.

The fine-tuning changes the model weights. It does not imply endorsement by
Howard Hughes Medical Institute or the upstream contributors.

The release's model card and version metadata identify the exact fine-tuned
checkpoint, its supported input conditions, and its evaluation limitations.
