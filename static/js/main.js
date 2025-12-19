async function vote(initiativeId, voteValue) {
    const response = await fetch('/api/vote', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            initiative_id: initiativeId,
            vote: voteValue
        })
    });

    const data = await response.json();
    if (data.success) {
        location.reload();
    } else {
        alert(data.message);
    }
}