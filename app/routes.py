# ============================================================
# ГЛАВНАЯ
# ============================================================
@bp.route("/")
@login_required
def index():
    tab = request.args.get("tab", "working")
    q = request.args.get("q", "").strip()
    sort_by = request.args.get("sort", "reg_date")

    query = Account.query

    if q:
        query = query.filter(
            (Account.email.ilike(f"%{q}%")) | (Account.nick.ilike(f"%{q}%"))
        )

    if sort_by == "status":
        query = query.order_by(Account.status.asc())
    else:
        query = query.order_by(Account.reg_date.desc())

    all_accounts = query.all()

    # Разбиваем на 4 вкладки
    for_sale = [a for a in all_accounts if a.is_for_sale_tab]
    working  = [a for a in all_accounts if a.is_working_tab]
    sold     = [a for a in all_accounts if a.is_sold_tab]
    invalid  = [a for a in all_accounts if a.is_invalid_tab]

    return render_template(
        "index.html",
        tab=tab,
        q=q,
        sort_by=sort_by,
        for_sale=for_sale,
        working=working,
        sold=sold,
        invalid=invalid,
        for_sale_count=len(for_sale),
        working_count=len(working),
        sold_count=len(sold),
        invalid_count=len(invalid),
    )