def cases():
    rows = []

    def add(name, group, body, expected, probe=None):
        rows.append(
            {
                "name": name,
                "group": group,
                "body": body.encode() if isinstance(body, str) else body,
                "expected": expected,
                "probe": probe,
            }
        )

    for name, body in [
        ("root-different", '{"text":"first","text":"second"}'),
        ("root-identical", '{"value":"same","value":"same"}'),
        ("root-escaped-name", '{"text":"a","\\u0074ext":"b"}'),
        ("root-escaped-both", '{"\\u0074ext":1,"\\u0074ext":2}'),
        ("root-escaped-slash", '{"a/b":1,"a\\/b":2}'),
        ("root-supplementary", '{"😀":1,"\\ud83d\\ude00":2}'),
        ("root-empty-name", '{"":1,"":2}'),
        ("root-conditional-flag", '{"if_absent":true,"if_absent":false}'),
        ("root-conditional-token", '{"if":"a","if":"b"}'),
        ("root-three", '{"x":1,"x":2,"x":3}'),
    ]:
        add(name, "root-duplicate", body, {"main": 204, "root-only": 400, "all-depth": 400})
    for name, body in [
        ("nested-object", '{"meta":{"a":1,"a":2}}'),
        ("nested-identical", '{"meta":{"a":1,"a":1}}'),
        ("nested-array", '{"meta":[{"a":1,"a":2}]}'),
        ("nested-deep", '{"meta":{"inner":{"a":1,"\\u0061":2}}}'),
        ("nested-empty", '{"meta":{"":1,"":2}}'),
        ("nested-supplementary", '{"meta":{"😀":1,"\\ud83d\\ude00":2}}'),
    ]:
        add(name, "nested-policy", body, {"main": 204, "root-only": 204, "all-depth": 400})
    for name, body, probe in [
        ("ordinary", '{"text":"hello","value":"ok"}', ("text", "hello")),
        ("colon-in-value", '{"text":"a:b:c"}', ("text", "a:b:c")),
        ("object-looking-string", '{"text":"{\\"a\\":1,\\"a\\":2}"}', None),
        ("same-in-siblings", '{"left":{"a":1},"right":{"a":2}}', None),
        ("same-in-array-siblings", '{"meta":[{"a":1},{"a":2}]}', None),
        ("same-root-and-child", '{"a":1,"meta":{"a":2}}', ("a", 1)),
        ("case-distinct", '{"Text":1,"text":2}', ("text", 2)),
        ("unicode-no-normalization", '{"é":1,"é":2}', None),
        ("boolean-and-null", '{"yes":true,"no":false,"missing":null}', ("yes", True)),
        ("finite-exponent", '{"x":1.25e3}', ("x", 1250)),
        ("empty-object", "{}", None),
        ("empty-body", b"", None),
    ]:
        add(
            name,
            "valid-control",
            body,
            dict.fromkeys(("main", "root-only", "all-depth"), 204),
            probe,
        )
    for name, body in [
        ("nan", '{"x":NaN}'),
        ("infinity", '{"x":Infinity}'),
        ("overflow", '{"x":1e400}'),
        ("trailing-comma", '{"a":1,}'),
        ("invalid-utf8", b'{"x":"\xff"}'),
        ("lone-surrogate", '{"x":"\\ud800"}'),
        ("root-array", "[]"),
        ("root-null", "null"),
        ("root-string", '"text"'),
        ("malformed-duplicate", '{"a":1,"a":}'),
    ]:
        add(name, "invalid-control", body, dict.fromkeys(("main", "root-only", "all-depth"), 400))
    for depth in (900, 980, 990, 1000, 1022, 1023):
        # The outer object adds one level: orjson accepts through total depth1024.
        add(
            f"array-depth-{depth}",
            "depth-observation",
            b'{"meta":' + b"[" * depth + b"0" + b"]" * depth + b"}",
            None,
        )
    return rows
