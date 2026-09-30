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

            # --- # による1行コメントの読み飛ばし ---
            if c == "#":
                while self.pos < len(self.text) and self.text[self.pos] != "\n":
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
    # 対象言語のBNF
    #   [] は省略可能、{} は0回以上の繰り返しを表す
    #
    # (* プログラム全体 *)
    # <program>       ::= { <var_decl> } <block>
    #
    # (* 変数宣言 *)
    # <var_decl>      ::= "var" <ident> { "," <ident> } [ ";" ]
    #
    # (* 文のブロック *)
    # <block>         ::= { <statement> [ ";" ] }
    #
    # (* 文 *)
    # <statement>     ::= <if_stmt>
    #                   | <while_stmt>
    #                   | <repeat_stmt>
    #                   | <assign_stmt>
    #                   | <read_stmt>
    #                   | <write_stmt>
    #
    # (* 各種文の構造 *)
    # <if_stmt>       ::= "if" <condition> "then" <block> [ "else" <block> ] "endif"
    # <while_stmt>    ::= "while" <condition> "do" <block> "done"
    # <repeat_stmt>   ::= "repeat" <block> "until" <condition>
    # <assign_stmt>   ::= <ident> ":=" <expression>
    # <read_stmt>     ::= "read" <ident>
    # <write_stmt>    ::= "write" <expression>
    #
    # (* 条件式と比較演算子 *)
    # <condition>     ::= <expression> <relop> <expression>
    # <relop>         ::= "=" | "<>" | "<" | ">" | "<=" | ">="
    #
    # (* 算術式（加減算） *)
    # <expression>    ::= <factor> { ( "+" | "-" ) <factor> }
    # <factor>        ::= <ident> | <number>

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
        # (* プログラム全体 *)
        # <program>       ::= { <var_decl> } <block>
        #
        # (* 変数宣言 *)
        # <var_decl>      ::= "var" <ident> { "," <ident> } [ ";" ]
        #
        self.labnum += 1
        start_label = f"L_{self.labnum:03d}"
        self.emit(f"\tjump\t{start_label}")
        self.emit(f"{start_label}:")

        # var_decl の処理
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
        # プログラム終了
        self.emit("\tjump\t0")

        # 定数領域と変数領域の宣言を出力
        for n in self.nums:
            self.emit(f"N_{n:03d}:")
            self.emit(f"\tlit\t{n}")
        for v in self.vars:
            self.emit(f"V_{v}:")
            self.emit("\tdecl\t1")

    def block(self):
        # (* 文のブロック *)
        # <block>         ::= { <statement> [ ";" ] }
        #
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
        # (* 文 *)
        # <statement>     ::= <if_stmt>
        #                   | <while_stmt>
        #                   | <repeat_stmt>
        #                   | <assign_stmt>
        #                   | <read_stmt>
        #                   | <write_stmt>
        #
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

    def _statement_if(self):
        # <if_stmt>       ::= "if" <condition> "then" <block> [ "else" <block> ] "endif"
        #
        self.eat(TokenType.IF)
        self.condition()
        self.eat(TokenType.THEN)

        self.labnum += 1
        exit_label_num = self.labnum
        self.emit(f"\tjump\tL_{exit_label_num:03d}")

        self.block()

        if self.tok.type == TokenType.ELSE:
            self.eat(TokenType.ELSE)
            self.block()
            # TODO: if-else のコード生成
            raise NotImplementedError("SSLCompiler._statement_if() のELSE部分のコード生成を実装してください。")
        self.emit(f"L_{exit_label_num:03d}:")

        self.eat(TokenType.ENDIF)

    def _statement_while(self):
        # <while_stmt>    ::= "while" <condition> "do" <block> "done"
        #
        self.eat(TokenType.WHILE)
        self.condition()
        self.eat(TokenType.DO)
        self.block()
        self.eat(TokenType.DONE)
        # TODO: while のコード生成
        raise NotImplementedError("SSLCompiler._statement_while() のコード生成を実装してください。")

    def _statement_repeat(self):
        # <repeat_stmt>   ::= "repeat" <block> "until" <condition>
        #
        self.eat(TokenType.REPEAT)
        self.block()
        self.eat(TokenType.UNTIL)
        self.condition()
        # TODO: repeat のコード生成
        raise NotImplementedError("SSLCompiler._statement_repeat() のコード生成を実装してください。")

    def _statement_assign(self):
        # <assign_stmt>   ::= <ident> ":=" <expression>
        #
        var_name = self.tok.value
        self.eat(TokenType.IDENT)
        self.eat(TokenType.ASSIGN)
        self.expression()
        self.emit(f"\tstore\tV_{var_name}")

    def _statement_read(self):
        # <read_stmt>     ::= "read" <ident>
        #
        self.eat(TokenType.READ)
        var_name = self.tok.value
        self.eat(TokenType.IDENT)
        self.emit(f"\tread\tV_{var_name}")

    def _statement_write(self):
        # <write_stmt>    ::= "write" <expression>
        #
        # TODO: 本来は expression を取るが IDENT だけに限定されている
        self.eat(TokenType.WRITE)
        var_name = self.tok.value
        self.eat(TokenType.IDENT)
        self.emit(f"\twrite\tV_{var_name}")

    def condition(self):
        # (* 条件式と比較演算子 *)
        # <condition>     ::= <expression> <relop> <expression>
        # <relop>         ::= "=" | "<>" | "<" | ">" | "<=" | ">="
        #
        self.expression()
        self.emit("\tstore\tV__tmp")
        op_tok = self.tok
        if op_tok.type == TokenType.GT:
            self.eat(TokenType.GT)
            self.expression()
            self.emit("\tsub\tV__tmp")
        else:
            # TODO: 他の演算子に対するコード生成
            raise NotImplementedError("SSLCompiler.condition() のコード生成の残りを実装してください。")

    def expression(self):
        if self.tok.type == TokenType.IDENT:
            self.emit(f"\tload\tV_{self.tok.value}")
            self.eat(TokenType.IDENT)
        elif self.tok.type == TokenType.NUMBER:
            val = int(self.tok.value)
            self.emit(f"\tload\tN_{self.add_num(val):03d}")
            self.eat(TokenType.NUMBER)

        while self.tok.type in (TokenType.PLUS, TokenType.MINUS):
            op = "add" if self.tok.type == TokenType.PLUS else "sub"
            self.eat(self.tok.type)
            if self.tok.type == TokenType.IDENT:
                self.emit(f"\t{op}\tV_{self.tok.value}")
                self.eat(TokenType.IDENT)
            elif self.tok.type == TokenType.NUMBER:
                val = int(self.tok.value)
                self.emit(f"\t{op}\tN_{self.add_num(val):03d}")
                self.eat(TokenType.NUMBER)

    def _extract_expression_code(self) -> list[str]:
        # expressionの生成するコードを返す
        saved_code = self.asm_code
        self.asm_code = []
        self.expression()
        expr_code = self.asm_code
        self.asm_code = saved_code
        return expr_code


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


SAMPLE_PROGRAM = """
var	x;
read x;
if x > 0 then
    x := 0 - x;
endif;
write x;
"""


if __name__ == "__main__":
    # --- 呼び出し方法の例 ---

    # 例1: ソースコード文字列を直接指定してテスト実行
    main(source_text=SAMPLE_PROGRAM)

    # 例2: ファイル名を直接指定してテスト実行
    # main(file="../samples/add_lang.ssl")

    # 例3: コマンドライン引数（または標準入力）から実行する通常動作
    # main()
