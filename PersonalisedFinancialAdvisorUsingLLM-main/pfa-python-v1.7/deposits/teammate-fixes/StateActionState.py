from datetime import date, timedelta
from pprint import pprint
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from GoalSearch import (GoalSearch, GOAL_REACHED, GOAL_NOT_REACHABLE,
                        GOAL_NOT_YET_REACHED)
import math


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
    balance: float = Field(
        description="Present bank balance or the lump sum amount of the user")
    time: date = Field(description="Present time stamp.")


class OptimalActionFixedDepositToolReturnsSchema(BaseModel):
    actionList: list[(deposit, int)] = Field(
        description=("Sequence of (deposit, "
                     "NumberOfTimesDepositToBeExecuted)s to be executed "
                     "by the user"))
    stateList: list[state] = Field(
        description=("Sequence of states reached after executing the "
                     "Sequence of deposits"))


class OptimalActionFixedDepositToolArgsSchema(BaseModel):
    s0: state = Field(description="Present state of the user")
    sg: state = Field(description="Goal state of the user")
    inflation: float = Field(description="Inflation rate of the country")
    deposits: list[deposit] = Field(
        description="list of popular bank deposit schemes")


@tool(args_schema=OptimalActionFixedDepositToolArgsSchema)
def OptimalActionFixedDepositTool(
        s0, sg, inflation, deposits
) -> OptimalActionFixedDepositToolReturnsSchema:
    """
    Returns list of optimal actions to be followed by the user.
    args:
      s0: Initial state of the user.
      sg: Goal state of the user.
      inflation: inflation rate of the country.
      deposits: list of popular bank deposit schemes.
    """
    # Sorting will speed up the search.
    oA = OptimalActionFixedDeposit(s0, sg, inflation, deposits)
    oA.printActionList()
    actionStateList = oA.getActionList()
    if not actionStateList:  # FIX: zip(*[]) crashed when nothing fits
        return [], []
    firsts, seconds = map(list, zip(*actionStateList))
    return firsts, seconds


class OptimalActionFixedDeposit():
    # Every work of the class is done in the init itself.
    def __init__(self, s0, sg, inflation, deposits):
        self.s0 = s0
        self.sg = sg
        self.inflation = inflation
        self.deposits = sorted(
            deposits, key=lambda x: self.sortBase(x), reverse=True)
        self.actionStateList = []
        gS = GoalSearch(self.sg, self.deposits,
                        self._finalBalance, self._reached)
        gS.BestSearch(self.s0)
        self.actionStateList = gS.getFinalList()

    def getActionList(self):
        return self.actionStateList

    def printActionList(self):
        pprint('Initial state')
        pprint(self.s0)
        pprint('Action list')
        pprint(self.actionStateList)
        pprint('Goal state')
        pprint(self.sg)

    def _reached(self, s, sg):
        if s.time <= sg.time:
            retVal = GOAL_REACHED if (
                s.balance >= sg.balance) else GOAL_NOT_YET_REACHED
        else:
            retVal = GOAL_NOT_REACHABLE
        return retVal

    def sortBase(self, deposit):
        return ((1 + (deposit.interestRate
                      * deposit.compoundingDuration / 100))
                ** ((deposit.duration / deposit.compoundingDuration)
                    * (math.floor(((self.sg.time - self.s0.time).days
                                   / (365 * deposit.duration))))))

    def _finalBalance(self, s, deposit):
        count = (math.floor(
            ((self.sg.time - s.time).days / (365 * deposit.duration))))
        if (0 == count):
            count = 1
        # FIX: deflate for every year the money is locked in (duration * count),
        # compounded. The original divided by (1 + duration * inflation) once,
        # so a 2-year FD renewed 5 times was only deflated for 2 years.
        return (state(balance=(s.balance
                               / ((1 + self.inflation / 100)
                                  ** (deposit.duration * count)))
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
                     "deposit in years"))
    scheme_name: str = Field(
        description="scheme name of the recurring deposit")
    bank_name: str = Field(
        description="bank name of the scheme name of the recurring deposit")


class stateR(BaseModel):
    balance: float = Field(
        description="Present installment planned by the user")
    time: date = Field(description="Present time stamp.")


class OptimalActionRecurringDepositToolReturnsSchema(BaseModel):
    actionList: list[(deposit, int)] = Field(
        description=("Sequence of (deposit, "
                     "NumberOfTimesDepositToBeExecuted)s to be executed "
                     "by the user"))
    stateList: list[state] = Field(
        description=("Sequence of states reached after executing the "
                     "Sequence of deposits"))


class OptimalActionRecurringDepositToolArgsSchema(BaseModel):
    s0: stateR = Field(
        description="Present state of the user's planned installment")
    sg: state = Field(description="Goal state of the user")
    inflation: float = Field(description="Inflation rate of the country")
    deposits: list[recurringDeposit] = Field(
        description="list of popular bank recurring deposit schemes")


@tool(args_schema=OptimalActionRecurringDepositToolArgsSchema)
def OptimalActionRecurringDepositTool(
        s0, sg, inflation, deposits
) -> OptimalActionRecurringDepositToolReturnsSchema:
    """
    Returns list of optimal actions to be followed by the user.
    args:
      s0: Initial state of the user's planned installment amount.
      sg: Goal state of the user.
      inflation: inflation rate of the country.
      deposits: list of popular recurring bank deposit schemes.
    """
    # Sorting will speed up the search.
    oA = OptimalActionRecurringDeposit(s0, sg, inflation, deposits)
    oA.printActionList()
    actionStateList = oA.getActionList()
    if not actionStateList:  # FIX: zip(*[]) crashed when nothing fits
        return [], []
    firsts, seconds = map(list, zip(*actionStateList))
    return firsts, seconds


class OptimalActionRecurringDeposit():
    # Every work of the class is done in the init itself.
    def __init__(self, s0, sg, inflation, recurringDeposits):
        self.s0 = s0
        self.sg = sg
        self.inflation = inflation
        # FIX: s0.balance is the monthly installment, not money saved. Keep it
        # apart and search from "nothing saved yet", so a later step does not
        # treat the previous maturity amount as its installment.
        self.installment = s0.balance
        self.deposits = sorted(
            recurringDeposits, key=lambda x: self.sortBase(x), reverse=True)
        self.actionStateList = []
        gS = GoalSearch(self.sg, self.deposits,
                        self._finalBalance, self._reached)
        gS.BestSearch(state(balance=0, time=s0.time))
        self.actionStateList = gS.getFinalList()

    def getActionList(self):
        return self.actionStateList

    def printActionList(self):
        pprint('Initial installment planned')
        pprint(self.s0)
        pprint('Recurring Action list')
        pprint(self.actionStateList)
        pprint('Goal state')
        pprint(self.sg)

    def _reached(self, s, sg):
        if s.time <= sg.time:
            retVal = GOAL_REACHED if (
                s.balance >= sg.balance) else GOAL_NOT_YET_REACHED
        else:
            retVal = GOAL_NOT_REACHABLE
        return retVal

    def _maturityPerRupee(self, deposit):
        # FIX: standard Indian bank RD maturity. Each monthly installment
        # compounds (quarterly by default) from the month it is paid until
        # maturity: M = sum over k of P * (1 + r*c/100) ** ((n - k + 1) * m / c)
        # where n installments of m years each, compounding every c years.
        # Rs 5,000 a month at 7% for 12 months -> about Rs 62,000. The original
        # expression gave about Rs 10.4 lakh for the same RD.
        n = max(1, round(deposit.duration / deposit.recurringDuration))
        q = 1 + deposit.interestRate * deposit.compoundingDuration / 100
        return sum(q ** ((n - k + 1) * deposit.recurringDuration
                         / deposit.compoundingDuration)
                   for k in range(1, n + 1))

    def sortBase(self, deposit):
        # FIX: rank by what Rs 1 a month grows to over the goal horizon
        # (the old key used the wrong maturity expression).
        count = math.floor((self.sg.time - self.s0.time).days
                           / (365 * deposit.duration))
        return self._maturityPerRupee(deposit) * count

    def _finalBalance(self, s, deposit):
        count = (math.floor(
            ((self.sg.time - s.time).days / (365 * deposit.duration))))
        if (0 == count):
            count = 1
        end = s.time + timedelta(days=(deposit.duration * count * 365))
        # Same RD renewed `count` times; matured amounts are kept (not
        # reinvested) and added to what was saved before.
        maturity = self.installment * self._maturityPerRupee(deposit) * count
        # FIX: deflate by the whole time from the start to maturity,
        # compounded (the original deflated one term only).
        years = (end - self.s0.time).days / 365
        return (state(balance=s.balance
                      + maturity / ((1 + self.inflation / 100) ** years),
                      time=end),
                count)
