def move_to_top_of_its_object(line):
    first_of_its_object = (
        line.get_ordering_queryset()
        .filter(item_type_id=line.item_type_id)
        .exclude(pk=line.pk)
        .first()
    )
    if first_of_its_object is None:
        line.top()
    else:
        line.above(first_of_its_object)
