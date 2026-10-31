from datetime import date, timedelta
from pprint import pprint
from pydantic import BaseModel, ConfigDict, Field, model_validator
from langchain_core.tools import tool
from GoalSearch import (GoalSearch, GOAL_NOT_REACHABLE,
                        GOAL_NOT_YET_REACHED)
import html
import math
import os
import networkx as nx

class deposit(BaseModel):
    interestRate: float = Field(
        description="Yearly Interest rate of the deposit in percent")
    duration: float = Field(
        description="total duration of the deposit in years")
    compoundingDuration: float = Field(
        description="Compounding duration of the deposit in years")
    scheme_name: str = Field(description="scheme name of the deposit")
    bank_name: str = Field(
        description="bank name of the scheme name of the deposit")


class state(BaseModel):
    # Frozen so states are hashable and can be graph nodes.
    model_config = ConfigDict(frozen=True)
    balance: float = Field(
        description="Present bank balance or the lump sum amount of the user")
    time: date = Field(description="Present time stamp.")


def _toMermaid(g):
    """Render a state graph as a mermaid flowchart description."""
    ids = {}

    def nodeId(st):
        key = (round(st.balance, 2), st.time)
        if key not in ids:
            ids[key] = f"n{len(ids)}"
        return ids[key]

    lines = ["graph TD;"]
    for st in g.nodes:
        lines.append(f'	{nodeId(st)}["balance: {st.balance:.2f}, '
                     f'date: {st.time}"];')
    for u, v, w in g.edges(data="weight"):
        # Fixed deposit edges carry (deposit, repeat count); recurring
        # deposit edges are unrolled and carry just the deposit.
        (dep, count) = w if isinstance(w, tuple) else (w, 1)
        # A double quote would end the mermaid label early.
        label = f"{dep.bank_name} {dep.scheme_name} x{count}".replace(
            '"', "'")
        lines.append(f'	{nodeId(u)} -->|"{label}"| {nodeId(v)};')
    # Leaf nodes (no outgoing action) are the final states: green. All the
    # other nodes: blue.
    leaves = [nodeId(st) for st in g.nodes if g.out_degree(st) == 0]
    others = [nodeId(st) for st in g.nodes if g.out_degree(st) > 0]
    if leaves:
        lines.append("\tclassDef leaf fill:#4caf50,stroke:#2e7d32,"
                     "color:#ffffff;")
        lines.append(f"\tclass {','.join(leaves)} leaf;")
    if others:
        lines.append("\tclassDef inner fill:#2196f3,stroke:#0d47a1,"
                     "color:#ffffff;")
        lines.append(f"\tclass {','.join(others)} inner;")
    return "\n".join(lines)

DEFAULT_DIAGRAM_FILE_NAME = "OptimalActionDiagrams.html"

class MermaidDiagram(BaseModel):
    name: str = Field(description="name (title) of the mermaid diagram")
    description: str = Field(description="mermaid textual description")

    @model_validator(mode="before")
    @classmethod
    def _fromPair(cls, data):
        # Also accept a (name, description) pair, as an LLM may send one.
        if isinstance(data, (list, tuple)) and len(data) == 2:
            return {"name": data[0], "description": data[1]}
        return data


OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")


def _diagramPath(path):
    """A folder (or a path without a file extension) gets the default
    file name; the parent folders are created. A relative path is placed
    in the project's "output" folder."""
    if not os.path.isabs(path):
        parts = os.path.normpath(path).split(os.sep)
        if parts[0] == "output":
            parts = parts[1:]
        path = os.path.join(OUTPUT_DIR, *parts)
    ext = os.path.splitext(path)[1]
    if os.path.isdir(path) or not ext:
        path = os.path.join(path, DEFAULT_DIAGRAM_FILE_NAME)
    elif ext.lower() != ".html":
        # The path comes from the LLM; never overwrite non-html files.
        raise ValueError(f"output path must be an .html file, got {path}")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    return path


def writeMermaidDiagramPage(diagrams, path):
    """Write diagrams to an HTML page that renders them with mermaid.js.

    diagrams: list of MermaidDiagram, (name, text) pairs or dicts.
    path: output .html file, or a folder to hold the default file name.
    Open the page in a browser; it loads mermaid.js from a CDN.
    Returns the path written.
    """
    diagrams = [d if isinstance(d, MermaidDiagram)
                else MermaidDiagram.model_validate(d) for d in diagrams]
    sections = "\n".join(
        f"<h2>{html.escape(d.name)}</h2>\n"
        f'<pre class="mermaid">{html.escape(d.description)}</pre>\n'
        f"<details><summary>mermaid text</summary>"
        f"<pre>{html.escape(d.description)}</pre></details>"
        for d in diagrams)
    page = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>Optimal action diagrams</title></head><body>"
        "<h1>Optimal action diagrams</h1>\n" + sections +
        "\n<script type='module'>"
        "import mermaid from "
        "'https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/"
        "mermaid.esm.min.mjs';"
        "mermaid.initialize({startOnLoad: true});</script>"
        "</body></html>")
    path = _diagramPath(path)
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    return path


class WriteMermaidDiagramPageReturnsSchema(BaseModel):
    path: str = Field(description="file path of the output diagram page")


class WriteMermaidDiagramPageArgsSchema(BaseModel):
    diagrams: list[MermaidDiagram] = Field(
        description="list of mermaid diagrams (name and mermaid description) "
                    "to be rendered")
    path: str = Field(
        description="output .html file path, or a folder path to put the "
                    "default file in")


@tool(args_schema=WriteMermaidDiagramPageArgsSchema)
def WriteMermaidDiagramPage(
        diagrams, path) -> WriteMermaidDiagramPageReturnsSchema:
    """Renders the mermaid descriptions as diagrams in an HTML page.
    args:
      diagrams: list of diagrams, each with a name and a mermaid description.
      path: output .html file path, or a folder path.
    return:
      path: output file path
    """
    return writeMermaidDiagramPage(diagrams, path)


class OptimalActionFixedDepositToolReturnsSchema(BaseModel):
    graphInText: str = Field(
        description=("fixed deposit sequence in the form of mermaid graph description"))


class OptimalActionFixedDepositToolArgsSchema(BaseModel):
    s0: state = Field(description="Present state of the user")
    sg: state = Field(description="Goal state of the user")
    deposits: list[deposit] = Field(
        description="list of popular bank deposit schemes")


@tool(args_schema=OptimalActionFixedDepositToolArgsSchema)
def OptimalActionFixedDepositTool(
        s0, sg, deposits
) -> OptimalActionFixedDepositToolReturnsSchema:
    """
    Returns list of optimal actions to be followed by the user.
    args:
      s0: Initial state of the user.
      sg: Goal state of the user.
      deposits: list of popular bank deposit schemes.
    """
    # Sorting will speed up the search.
    g = nx.DiGraph()
    if s0.balance > 0:
        oA = OptimalActionFixedDeposit(s0, sg, deposits)
        g.update(oA.getActionList()[0])
    return _toMermaid(g)

class OptimalActionFixedDeposit:
    # Every work of the class is done in the init itself.
    def __init__(self, s0, sg, deposits):
        assert s0.balance > 0, (
            f"start balance must be positive, got {s0.balance}")
        assert sg.balance > 0, (
            f"goal balance must be positive, got {sg.balance}")
        self.G = nx.DiGraph()
        self.stStActList = []
        self.s0 = s0
        self.sg = sg
        self.deposits = sorted(
            deposits, key=lambda x: self.sortBase(x), reverse=True)
        actionStateList1 = []
        self.actionStateList = []
        gS = GoalSearch(self.sg, self.deposits,
                        self._finalBalance, self._reached)
        gS.BestSearch(state(balance=s0.balance, time=s0.time))
        actionStateList1, self.fallShortAmount = gS.getFinalList()
        for each in actionStateList1:
            self.actionStateList.append(
                ((self.deposits[each[0][0]], each[0][1]), each[1]))

    def getActionList(self):
        #Find the list of (state, state, (action,c))
        St = self.s0
        for eachActionState in self.actionStateList:
            nextSt = eachActionState[1]
            self.stStActList.append((St, nextSt, eachActionState[0]))
            St = nextSt
        self.G.add_weighted_edges_from(self.stStActList)
        return self.G, self.fallShortAmount

    def printActionList(self):
        pprint('Initial state')
        pprint(self.s0)
        pprint('Action list')
        pprint(self.actionStateList)
        pprint('Goal state')
        pprint(self.sg)

    def _reached(self, s, sg):
        if s.time <= sg.time:
            retVal = GOAL_NOT_YET_REACHED
        else:
            retVal = GOAL_NOT_REACHABLE
        return retVal

    def sortBase(self, deposit):
        assert deposit.interestRate > 0, (
            f"interestRate must be positive, got {deposit.interestRate} "
            f"for {deposit.bank_name} {deposit.scheme_name}")
        assert deposit.duration > 0, (
            f"duration must be positive, got {deposit.duration} "
            f"for {deposit.bank_name} {deposit.scheme_name}")
        assert deposit.compoundingDuration > 0, (
            f"compoundingDuration must be positive, got "
            f"{deposit.compoundingDuration} "
            f"for {deposit.bank_name} {deposit.scheme_name}")
        return ((1 + (deposit.interestRate
                      * deposit.compoundingDuration / 100))
                ** ((deposit.duration / deposit.compoundingDuration)
                    * (math.floor(((self.sg.time - self.s0.time).days
                                   / (365 * deposit.duration))))))

    def _finalBalance(self, s, deposit):
        assert deposit.interestRate > 0, (
            f"interestRate must be positive, got {deposit.interestRate} "
            f"for {deposit.bank_name} {deposit.scheme_name}")
        assert deposit.duration > 0, (
            f"duration must be positive, got {deposit.duration} "
            f"for {deposit.bank_name} {deposit.scheme_name}")
        assert deposit.compoundingDuration > 0, (
            f"compoundingDuration must be positive, got "
            f"{deposit.compoundingDuration} "
            f"for {deposit.bank_name} {deposit.scheme_name}")
        count = (math.floor(
            ((self.sg.time - s.time).days / (365 * deposit.duration))))
        if 0 == count:
            count = 1
        return (state(balance=s.balance
                      * ((1 + (deposit.interestRate
                               * deposit.compoundingDuration / 100))
                         ** ((deposit.duration
                              / deposit.compoundingDuration) * count)),
                      time=s.time + timedelta(
                          days=(deposit.duration * count * 365))),
                count)


class recurringDeposit(BaseModel):
    interestRate: float = Field(
        description="Yearly Interest rate of the recurring deposit in percent")
    duration: float = Field(
        description="total duration of the recurring deposit in years")
    compoundingDuration: float = Field(
        description="Compounding duration of the recurring deposit in years")
    recurringDuration: float = Field(
        description=("time period of the installment of the recurring "
                     "deposit in months"))
    scheme_name: str = Field(
        description="scheme name of the recurring deposit")
    bank_name: str = Field(
        description="bank name of the scheme name of the recurring deposit")


class stateR(BaseModel):
    # Frozen so states are hashable and can be graph nodes.
    model_config = ConfigDict(frozen=True)
    balance: float = Field(
        description="Present installment planned by the user")
    time: date = Field(description="Present time stamp.")


class OptimalActionRecurringDepositToolReturnsSchema(BaseModel):
    graphInText: str = Field(
        description=("deposit sequence in the form of mermaid graph description"))


class OptimalActionRecurringDepositToolArgsSchema(BaseModel):
    s0: stateR = Field(
        description="Present state of the user's planned installment")
    sg: state = Field(description="Goal state of the user")
    recurringDeposits: list[recurringDeposit] = Field(
        description="list of popular bank recurring deposit schemes")
    fixedDeposits: list[deposit] = Field(
        description="list of popular bank fixed deposit schemes")


@tool(args_schema=OptimalActionRecurringDepositToolArgsSchema)
def OptimalActionRecurringDepositTool(
        s0, sg, recurringDeposits, fixedDeposits
) -> OptimalActionRecurringDepositToolReturnsSchema:
    """
    Returns list of optimal actions to be followed by the user.
    args:
      s0: Initial state of the user's planned installment amount.
      sg: Goal state of the user.
      recurringDeposits: list of popular recurring bank deposit schemes.
      fixedDeposits: list of popular recurring bank fixed deposit schemes.
    """
    # Sorting will speed up the search.
    g = nx.DiGraph()
    if s0.balance > 0:
        oA = OptimalActionRecurringDeposit(s0, sg, recurringDeposits)
        g.update(oA.getActionList()[0])
        # Every state after the first holds the matured recurring deposit
        # amount, which can then be put into fixed deposits.
        for node in list(g.nodes)[1:]:
            if node.balance > 0 and node.time < sg.time:
                oA1 = OptimalActionFixedDeposit(
                    state(balance=node.balance, time=node.time),
                    sg, fixedDeposits)
                g.update(oA1.getActionList()[0])
    return _toMermaid(g)

class OptimalActionRecurringDeposit:
    # Every work of the class is done in the init itself.
    def __init__(self, s0, sg, recurringDeposits):
        assert s0.balance > 0, (
            f"start balance must be positive, got {s0.balance}")
        assert sg.balance > s0.balance, (
            f"goal balance {sg.balance} must be greater than "
            f"start balance {s0.balance}")
        self.stStActList = []
        self.G = nx.DiGraph()
        self.s0 = s0
        self.sg = sg
        self.deposits = sorted(
            recurringDeposits, key=lambda x: self.sortBase(x), reverse=True)
        actionStateList1 = []
        self.actionStateList = []
        gS = GoalSearch(self.sg, self.deposits,
                        self._finalBalance, self._reached)
        gS.BestSearch(state(balance=s0.balance, time=s0.time))
        actionStateList1, self.fallShortAmount = gS.getFinalList()
        for each in actionStateList1:
            self.actionStateList.append(
                ((self.deposits[each[0][0]], each[0][1]), each[1]))

    def getActionList(self):
        #Find the list of (state, state, (action,c))
        time = self.s0.time
        initBalance = self.s0.balance
        for eachActionState in self.actionStateList:
            (dep, count), nextSt = eachActionState
            deltaTime = timedelta(days=dep.duration * 365)
            # A repeated action is split into one edge per repetition; the
            # balance grows evenly so the last repetition ends at the full
            # balance of the action.
            endBalance = nextSt.balance / count
            for i in range(1, count + 1):
                self.stStActList.append(
                    (state(balance=initBalance, time=time),
                     state(balance=endBalance, time=time + deltaTime),
                     dep))
                time = time + deltaTime
                initBalance = endBalance
            time = nextSt.time
        self.G.add_weighted_edges_from(self.stStActList)
        return self.G, self.fallShortAmount

    def printActionList(self):
        pprint('Initial installment planned')
        pprint(self.s0)
        pprint('Recurring Action list')
        pprint(self.actionStateList)
        pprint('Goal state')
        pprint(self.sg)

    def _reached(self, s, sg):
        if s.time <= sg.time:
            retVal = GOAL_NOT_YET_REACHED
        else:
            retVal = GOAL_NOT_REACHABLE
        return retVal

    def sortBase(self, deposit):
        # qw1 below is zero for a zero rate, which would divide by zero.
        assert deposit.interestRate > 0, (
            f"interestRate must be positive, got {deposit.interestRate} "
            f"for {deposit.bank_name} {deposit.scheme_name}")
                # exp1 and exp2 below divide by the compounding duration.
        assert deposit.compoundingDuration > 0, (
            f"compoundingDuration must be positive, got "
            f"{deposit.compoundingDuration} "
            f"for {deposit.bank_name} {deposit.scheme_name}")
        ar = (1 + ((deposit.interestRate / 100)
                   * deposit.compoundingDuration))
        exp1 = ((deposit.recurringDuration / 12)
                / deposit.compoundingDuration)
        qw1 = ((ar ** exp1) - 1)

        exp2 = ((deposit.duration) / deposit.compoundingDuration)
        qw2 = (ar ** exp2) - 1

        qw3 = (ar ** exp1)
        w = qw3 * qw2 / qw1
        return w

    def _finalBalance(self, s, deposit):
        # qw1 below is zero for a zero rate, which would divide by zero.
        assert deposit.interestRate > 0, (
            f"interestRate must be positive, got {deposit.interestRate} "
            f"for {deposit.bank_name} {deposit.scheme_name}")
        # count below divides by the duration.
        assert deposit.duration > 0, (
            f"duration must be positive, got {deposit.duration} "
            f"for {deposit.bank_name} {deposit.scheme_name}")
        # exp1 and exp2 below divide by the compounding duration.
        assert deposit.compoundingDuration > 0, (
            f"compoundingDuration must be positive, got "
            f"{deposit.compoundingDuration} "
            f"for {deposit.bank_name} {deposit.scheme_name}")
        count = (math.floor(
            ((self.sg.time - s.time).days / (365 * deposit.duration))))
        if 0 == count:
            count = 1
        ar = (1 + ((deposit.interestRate / 100)
                   * deposit.compoundingDuration))
        exp1 = ((deposit.recurringDuration / 12)
                / deposit.compoundingDuration)
        qw1 = ((ar ** exp1) - 1)

        exp2 = ((deposit.duration) / deposit.compoundingDuration)
        qw2 = (ar ** exp2) - 1

        qw3 = (ar ** exp1)
        w = qw3 * qw2 / qw1
        return (state(balance=(self.s0.balance
                               * w * count),
                      time=s.time + timedelta(
                          days=(deposit.duration * count * 365))), count)


class GetFinalValueConsideringInflationReturnsSchema(BaseModel):
    endValue: float = Field(
        description="Value of the deposits at the goal time")


class GetFinalValueConsideringInflationArgsSchema(BaseModel):
    startTime: date = Field(description="Present date")
    goalTime: date = Field(
        description=("goal date specified by the user"))
    endBalance: float = Field(
        description=("Amount at the end of fruitioning of all deposits"))
    inflation: float = Field(description="Inflation rate of the country")


@tool(args_schema=GetFinalValueConsideringInflationArgsSchema)
def GetFinalValueConsideringInflation(startTime, goalTime, endBalance,
                                      inflation):
    """
    Returns the Value balance at the goal time.
    args:
      startTime: present date
      goalTime: goal date
      endBalance: amount at the goal date
      inflation: inflation rate of the country.
    """
    n = (goalTime - startTime).days / 365
    return endBalance / ((1 + (inflation / 100))**n)
