import enum
import sys
from dataclasses import dataclass


class TokenType(enum.Enum):
    VAR = "var"
    IF = "if"
    THEN = "then"
    ENDIF = "endif"
    ELSE = "else"
    WHILE = "while"
    DO = "do"
    DONE = "done"
    REPEAT = "repeat"
    UNTIL = "until"
    READ = "read"
    WRITE = "write"

    IDENT = "<IDENT>"
    NUMBER = "<NUMBER>"
    EOF = "<EOF>"

    ASSIGN = ":="
    EQ = "="
    NE = "<>"
    LT = "<"
    GT = ">"
    LE = "<="
    GE = ">="

    PLUS = "+"
    MINUS = "-"
    COMMA = ","
    SEMI = ";"


@dataclass
class Token:
    type: TokenType
    value: str
    line: int


class Lexer:
    """SSL言語の字句解析器 (完全提供コード)"""

    KEYWORDS = {
        token.value: token for token in TokenType if token.value.isalpha()
    }
    OPS_TWO = {
        token.value: token
        for token in TokenType
        if len(token.value) == 2 and not token.value.startswith("<")
    }
    OPS_ONE = {token.value: token for token in TokenType if len(token.value) == 1}

    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.line = 1

    def error(self, msg: str):
        raise SyntaxError(f"Lexer error at line {self.line}: {msg}")

    def get_next_token(self) -> Token:
        while self.pos < len(self.text):
            c = self.text[self.pos]

            if c == "\n":
                self.line += 1
                self.pos += 1
                continue
            if c.isspace():
                self.pos += 1
                continue

            if c.isalpha():
                start = self.pos
                while self.pos < len(self.text) and (
                    self.text[self.pos].isalnum() or self.text[self.pos] == "_"
                ):
                    self.pos += 1
                val = self.text[start : self.pos]
                token_type = self.KEYWORDS.get(val, TokenType.IDENT)
                return Token(token_type, val, self.line)

            if c.isdigit():
                start = self.pos
                while self.pos < len(self.text) and self.text[self.pos].isdigit():
                    self.pos += 1
                return Token(
                    TokenType.NUMBER, self.text[start : self.pos], self.line
                )

            two_char = self.text[self.pos : self.pos + 2]
            if two_char in self.OPS_TWO:
                self.pos += 2
                return Token(self.OPS_TWO[two_char], two_char, self.line)

            if c in self.OPS_ONE:
                self.pos += 1
                return Token(self.OPS_ONE[c], c, self.line)

            self.error(f"Unexpected character '{c}'")

        return Token(TokenType.EOF, "", self.line)


class SSLCompiler:
    """【第3回 課題】SSL言語 (.ssl) から SSCアセンブリ (.sss) を生成するコンパイラ"""

    def __init__(self):
        self.lexer: Lexer | None = None
        self.tok: Token | None = None
        self.vars: list[str] = []
        self.nums: list[int] = []
        self.labnum = 0
        self.asm_code: list[str] = []

    def error(self, msg: str):
        line = self.tok.line if self.tok else 0
        raise SyntaxError(f"Compile error at line {line}: {msg}")

    def eat(self, token_type: TokenType):
        if self.tok.type == token_type:
            self.tok = self.lexer.get_next_token()
        else:
            self.error(
                f"Expected {token_type.name}, got {self.tok.type.name} ('{self.tok.value}')"
            )

    def add_var(self, name: str):
        if name not in self.vars:
            self.vars.append(name)

    def add_num(self, n: int) -> int:
        n = (n + 256) % 256
        if n not in self.nums:
            self.nums.append(n)
        return n

    def emit(self, code: str):
        self.asm_code.append(code)

    def compile(self, source_code: str) -> str:
        self.lexer = Lexer(source_code)
        self.tok = self.lexer.get_next_token()
        self.vars.clear()
        self.nums.clear()
        self.labnum = 0
        self.asm_code.clear()

        self.program()
        return "\n".join(self.asm_code)

    def program(self):
        self.labnum += 1
        start_label = f"L_{self.labnum:03d}"
        self.emit(f"\tjump\t{start_label}")
        self.emit(f"{start_label}:")

        while self.tok.type == TokenType.VAR:
            self.eat(TokenType.VAR)
            while True:
                if self.tok.type == TokenType.IDENT:
                    self.add_var(self.tok.value)
                    self.eat(TokenType.IDENT)
                if self.tok.type == TokenType.COMMA:
                    self.eat(TokenType.COMMA)
                else:
                    break
            if self.tok.type == TokenType.SEMI:
                self.eat(TokenType.SEMI)

        self.block()
        self.eat(TokenType.EOF)
        self.emit("\tjump\t0")

        # 定数領域と変数領域の宣言を出力
        for n in self.nums:
            self.emit(f"N_{n:03d}:")
            self.emit(f"\tlit\t{n}")

        for v in self.vars:
            self.emit(f"V_{v}:")
            self.emit("\tdecl\t1")

    def block(self):
        while self.tok.type in (
            TokenType.IF,
            TokenType.WHILE,
            TokenType.REPEAT,
            TokenType.IDENT,
            TokenType.READ,
            TokenType.WRITE,
        ):
            self.statement()
            if self.tok.type == TokenType.SEMI:
                self.eat(TokenType.SEMI)

    def statement(self):
        if self.tok.type == TokenType.IF:
            self._statement_if()
        elif self.tok.type == TokenType.WHILE:
            self._statement_while()
        elif self.tok.type == TokenType.REPEAT:
            self._statement_repeat()
        elif self.tok.type == TokenType.IDENT:
            self._statement_assign()
        elif self.tok.type == TokenType.READ:
            self._statement_read()
        elif self.tok.type == TokenType.WRITE:
            self._statement_write()

    def _eval_expression(self) -> list[str]:
        """式評価コードを評価バッファに分離して生成するヘルパー関数"""
        saved_code = self.asm_code
        self.asm_code = []
        self.expression()
        expr_code = self.asm_code
        self.asm_code = saved_code
        return expr_code

    # -----------------------------------------------------------------
    # 【課題1】基本文（代入・IO文・式評価）のコード生成
    # -----------------------------------------------------------------

    def _statement_assign(self):
        """代入文 (IDENT := EXPR) のコード生成"""
        var_name = self.tok.value
        self.eat(TokenType.IDENT)
        self.eat(TokenType.ASSIGN)

        # TODO: _eval_expression() を呼び出して右辺の評価コードを取得し、
        # self.asm_code に追加した上で、結果を変数 (V_var_name) に store する命令を出力せよ。
        raise NotImplementedError("_statement_assign() を実装してください")

    def _statement_read(self):
        """入力文 (read IDENT) のコード生成"""
        self.eat(TokenType.READ)
        var_name = self.tok.value
        self.eat(TokenType.IDENT)
        self.emit(f"\tread\tV_{var_name}")

    def _statement_write(self):
        """出力文 (write EXPR) のコード生成"""
        self.eat(TokenType.WRITE)
        self.add_var("_tmp")
        expr_code = self._eval_expression()
        self.asm_code.extend(expr_code)
        self.emit("\tstore\tV__tmp")
        self.emit("\twrite\tV__tmp")

    def expression(self):
        """項および加減算 (EXPR + EXPR / EXPR - EXPR) の評価"""
        if self.tok.type == TokenType.IDENT:
            self.emit(f"\tload\tV_{self.tok.value}")
            self.eat(TokenType.IDENT)
        elif self.tok.type == TokenType.NUMBER:
            val = int(self.tok.value)
            self.emit(f"\tload\tN_{self.add_num(val):03d}")
            self.eat(TokenType.NUMBER)

        # TODO: WHILE ループで TokenType.PLUS または TokenType.MINUS を巡回し、
        # 後続の IDENT や NUMBER の値を load/add/sub するアセンブリを出力せよ。
        raise NotImplementedError("expression() を実装してください")

    # -----------------------------------------------------------------
    # 【課題2】制御文（IF, WHILE, REPEAT）と条件式のコード生成
    # -----------------------------------------------------------------

    def _statement_if(self):
        """条件分岐 (if COND then BLOCK [else BLOCK] endif) のコード生成"""
        self.eat(TokenType.IF)

        # TODO:
        # 1. self.condition() を呼び出して条件判定ロジックを出力
        # 2. 偽の場合の飛び先ラベル (L_else) を生成し、jump 命令を出力
        # 3. self.block() を呼び出して THEN 節のブロックを出力
        # 4. ELSE 節が存在する場合は、THEN 節の末尾に EXIT 用ラベルへの jump 命令を出力し、
        #    ELSE 節のブロックを出力せよ
        raise NotImplementedError("_statement_if() を実装してください")

    def _statement_while(self):
        """ループ文 (while COND do BLOCK done) のコード生成"""
        self.eat(TokenType.WHILE)

        # TODO:
        # 1. ループ先頭ラベル (L_loop) を生成し出力
        # 2. self.condition() で条件判定コードを出力し、偽の際の脱出ラベル (L_exit) へ jump 命令を出力
        # 3. DO ブロック (self.block()) を処理後、先頭ラベル (L_loop) へ戻る jump 命令を出力
        # 4. 脱出ラベル (L_exit) を出力せよ
        raise NotImplementedError("_statement_while() を実装してください")

    def _statement_repeat(self):
        """ループ文 (repeat BLOCK until COND) のコード生成"""
        self.eat(TokenType.REPEAT)

        # TODO:
        # 1. ループ先頭ラベルを生成し出力
        # 2. self.block() で本体ブロックを処理
        # 3. UNTIL 節を処理し、条件が成立するまで先頭ラベルへ jump するロジックを実装せよ
        raise NotImplementedError("_statement_repeat() を実装してください")

    def condition(self):
        """比較条件式のコード生成 (>, <, =, <>, >=, <=)"""
        self.add_var("_tmp")
        buf1 = self._eval_expression()

        op_tok = self.tok
        if op_tok.type in (
            TokenType.GT,
            TokenType.LT,
            TokenType.EQ,
            TokenType.NE,
            TokenType.GE,
            TokenType.LE,
        ):
            self.eat(op_tok.type)
        else:
            self.error("Expected comparison operator (>, <, =, <>, >=, <=)")

        buf2 = self._eval_expression()

        # TODO: 比較演算子に応じた AC の正負判定ロジックを生成せよ
        # SSC の JUMP 命令は「AC >= 0 のときにジャンプする」仕様であることを利用すること。
        raise NotImplementedError("condition() を実装してください")


def main(
    args_list: list[str] | None = None,
    file: str | None = None,
    source_text: str | None = None,
):
    import argparse

    parser = argparse.ArgumentParser(
        prog="ssc_comp", description="SSL Compiler (Compiler to .sss)"
    )
    parser.add_argument(
        "file", nargs="?", type=str, default=None, help="Input .ssl file"
    )

    parsed_args = parser.parse_args(args_list)
    target_file = file if file is not None else parsed_args.file

    if source_text is None:
        if target_file:
            try:
                with open(target_file, "r", encoding="utf-8") as f:
                    source_text = f.read()
            except OSError as e:
                sys.stderr.write(f"ssc_comp: {e}\n")
                sys.exit(2)
        else:
            source_text = sys.stdin.read()

    compiler = SSLCompiler()
    try:
        asm_output = compiler.compile(source_text)
        print(asm_output)
    except (SyntaxError, NotImplementedError) as e:
        sys.stderr.write(f"ssc_comp error: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
