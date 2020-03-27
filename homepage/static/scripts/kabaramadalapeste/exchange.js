let data = {};

let prop_to_img = {
    SK: "/static/images/game/coins.png",
    K1: "/static/images/game/key1.png",
    K2: "/static/images/game/key2.png",
    K3: "/static/images/game/key3.png",
    VIS: "/static/images/game/look.png",
    TXP: "/static/images/game/attraction.png",
    CHP: "/static/images/game/problem.png",
    BLY: "/static/images/game/trap.png"
};

get_player_info()
    .then(response => {
        if (response.currently_anchored) {
            $(".back-to-island").css("display", "inline-block");
        }
        data.username = response.username;
    })
    .then(get_all_offers)
    .then(response => {
        response.offers.forEach(offer => {
            let offer_template = $(".offer-template");
            let offer_item_template = $(".offer-item-template");

            offer_template
                .find(".offer-username")
                .text(offer.creator_participant_username);
            offer_template
                .find(".offer-suggested-list")
                .html("<div class='exchange-type'>+</div>");
            offer_template
                .find(".offer-requested-list")
                .html("<div class='exchange-type'>-</div>");
            for (const key in offer) {
                if (offer.hasOwnProperty(key)) {
                    let property, property_type;
                    if (key.startsWith("suggested_")) {
                        property_type = "suggested";
                        property = key.replace("suggested_", "");
                    } else if (key.startsWith("requested_")) {
                        property_type = "requested";
                        property = key.replace("requested_", "");
                    } else {
                        continue;
                    }
                    if (offer[key]) {
                        offer_item_template
                            .find(".offer-item-number")
                            .text(offer[key]);
                        offer_item_template
                            .find("img")
                            .attr("src", prop_to_img[property]);
                        offer_template
                            .find(".offer-" + property_type + "-list")
                            .append(offer_item_template.html());
                    }
                }
            }

            offer_template.find(".offer-btns a").attr("data-pk", offer.pk);

            if (data.username === offer.creator_participant_username) {
                offer_template.find(".exchange-card").removeClass("acc-offer");
                offer_template.find(".exchange-card").addClass("del-offer");
                $(".my-offers .exchanges-list").append(offer_template.html());
            } else {
                offer_template.find(".exchange-card").addClass("acc-offer");
                offer_template.find(".exchange-card").removeClass("del-offer");
                $(".all-offers .exchanges-list").append(offer_template.html());
            }
        });
    })
    .then(() => {
        $(".offer-btns a").click(function() {
            let title = "مبادله";
            let question = "آیا مبادله را می‌پذیرید؟";
            let kind = "accept";
            if ($(this).hasClass("delete-offer")) {
                title = "حذف پیشنهاد";
                question = "آیا می‌خواهید پیشنهاد خود را حذف کنید؟";
                kind = "delete";
            }
            my_prompt(question, title, {
                kind: kind,
                pk: $(this).data("pk")
            });
            $("#prompt_modal").modal("show");
        });
    })
    .catch(default_fail);

$("#prompt_modal_btn").click(function() {
    switch ($(this).data("kind")) {
        case "accept":
            accept_offer($(this).data("pk"))
                .then(() => {
                    my_alert("مبادله با موفقیت انجام شد.", "مبادله");
                    setTimeout(function() {
                        window.location.href = "/game/exchange/";
                    }, 1000);
                })
                .catch(default_fail);
            break;
        case "delete":
            delete_offer($(this).data("pk"))
                .then(() => {
                    my_alert("حذف پیشنهاد با موفقیت انجام شد.", "حذف پیشنهاد");
                    setTimeout(function() {
                        window.location.href = "/game/exchange/";
                    }, 1000);
                })
                .catch(default_fail);
            break;

        default:
            break;
    }
});

$("#add_exchange_modal_btn").click(function() {
    create_offer($("#add_exchange_modal form"))
        .then(() => {
            my_alert("پیشنهاد شما ثبت شد.", "پیشنهاد");
            setTimeout(function() {
                window.location.href = "/game/exchange/";
            }, 1000);
        })
        .catch(default_fail);
});
