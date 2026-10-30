"""STEP24 환경 점검 + 사전학습 가중치 안전 변환 + 입력 길이 분포.

- 원본: models/pretrained_koelectra_small_main/pytorch_model.bin (HF main 커밋 고정, 소유자 업로드)
- torch.load(weights_only=True) 로만 읽고 safetensors 로 저장(임의 코드 실행 차단). 미병합 PR 변환본은 쓰지 않는다.
- max_length: 32/64 중 학습·dev·test 문장의 99% 이상(최대 포함)을 담는 가장 작은 값.
출력: outputs/environment.json · data/label_map.json
"""
import platform
import shutil

import torch

import s24_common as S


def main():
    from safetensors.torch import save_file
    import transformers
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    S.PRETRAINED.mkdir(exist_ok=True)
    sd = torch.load(S.PRETRAINED_SRC / "pytorch_model.bin", map_location="cpu", weights_only=True)
    sd = {k: v.contiguous() for k, v in sd.items()}
    save_file(sd, str(S.PRETRAINED / "model.safetensors"), metadata={"format": "pt"})
    for f in ("config.json", "vocab.txt", "tokenizer_config.json"):
        shutil.copyfile(S.PRETRAINED_SRC / f, S.PRETRAINED / f)

    lm = S.label_map()
    lin, _ = S.linear_model()
    assert list(lin.classes_) == list(lm), "label map ≠ LinearSVC classes_"
    S.dump_json(S.DATA / "label_map.json", lm)

    tok = AutoTokenizer.from_pretrained(S.PRETRAINED)
    model = AutoModelForSequenceClassification.from_pretrained(S.PRETRAINED, num_labels=len(lm))
    n_params = sum(p.numel() for p in model.parameters())
    X, _ = S.train_data()
    gold, _, _ = S.eval_sets()
    lens = sorted(len(tok(t)["input_ids"]) for t in X + [S.norm(g["text_ko"]) for g in gold])
    q = {p: lens[min(len(lens) - 1, int(p * len(lens)))] for p in (0.5, 0.9, 0.99)}
    max_len = next(L for L in (32, 64) if q[0.99] <= L and lens[-1] <= L) if lens[-1] <= 64 else 64
    unk = sum(t == tok.unk_token_id for x in X[:200] for t in tok(x)["input_ids"])

    cuda = torch.cuda.is_available()
    env = {"python": platform.python_version(), "torch": torch.__version__, "torch_cuda": torch.version.cuda, "cuda_available": cuda,
           "gpu_name": torch.cuda.get_device_name(0) if cuda else None,
           "gpu_total_vram_mib": round(torch.cuda.get_device_properties(0).total_memory / 2 ** 20) if cuda else None,
           "transformers": transformers.__version__,
           "model": {"repository": S.HF_REPO, "revision": S.HF_REVISION, "license": "Apache-2.0 (upstream github.com/monologg/KoELECTRA LICENSE; HF card has no license field)",
                     "download_dir": str(S.PRETRAINED_SRC.relative_to(S.STEP)),
                     "files": {f.name: {"bytes": f.stat().st_size, "sha256": S.sha256(f)} for f in sorted(S.PRETRAINED_SRC.glob("*")) if f.is_file()},
                     "total_bytes": sum(f.stat().st_size for f in S.PRETRAINED_SRC.glob("*") if f.is_file()),
                     "converted_safetensors_sha256": S.sha256(S.PRETRAINED / "model.safetensors"),
                     "n_params_with_77_head": n_params, "missing_keys_note": "classifier head 는 새로 초기화(정상)"},
           "n_labels": len(lm), "token_length_quantiles": q, "token_length_max": lens[-1], "n_texts_measured": len(lens),
           "selected_max_length": max_len, "unk_tokens_in_first_200_train": unk}
    S.dump_json(S.OUT / "environment.json", env)
    print(env)


if __name__ == "__main__":
    main()
