#include "Core/SessionJson.hh"

#include <cmath>
#include <set>
#include <utility>
#include <vector>

namespace SessionJson {
namespace {

class StrictSaxHandler final : public nlohmann::json_sax<Json> {
public:
    bool null() override { return emit(Json(nullptr)); }
    bool boolean(bool value) override { return emit(Json(value)); }

    bool number_integer(number_integer_t value) override { return emit(Json(value)); }

    bool number_unsigned(number_unsigned_t value) override { return emit(Json(value)); }

    bool number_float(number_float_t value, const string_t&) override
    {
        if (!std::isfinite(value)) {
            return fail("non_finite_number");
        }
        return emit(Json(value));
    }

    bool string(string_t& value) override
    {
        if (value.size() > kMaxStringBytes) {
            return fail("string_too_long");
        }
        return emit(Json(std::move(value)));
    }

    bool binary(binary_t&) override { return fail("binary_value"); }

    bool start_object(std::size_t) override
    {
        if (frames_.size() >= static_cast<std::size_t>(kMaxDepth)) {
            return fail("document_too_deep");
        }
        frames_.push_back(Frame{Json::object(), {}, std::string(), true});
        return true;
    }

    bool key(string_t& value) override
    {
        if (frames_.empty() || !frames_.back().isObject) {
            return fail("key_outside_object");
        }
        if (value.size() > kMaxStringBytes) {
            return fail("string_too_long");
        }
        if (!frames_.back().keys.insert(value).second) {
            return fail("duplicate_key");
        }
        frames_.back().pendingKey = std::move(value);
        return true;
    }

    bool end_object() override { return finishContainer(); }

    bool start_array(std::size_t) override
    {
        if (frames_.size() >= static_cast<std::size_t>(kMaxDepth)) {
            return fail("document_too_deep");
        }
        frames_.push_back(Frame{Json::array(), {}, std::string(), false});
        return true;
    }

    bool end_array() override { return finishContainer(); }

    bool parse_error(std::size_t, const std::string&,
                     const nlohmann::detail::exception& error) override
    {
        return fail(std::string("invalid_json: ") + error.what());
    }

    bool ok() const { return !failed_; }
    const std::string& error() const { return error_; }
    const Json& root() const { return root_; }

private:
    struct Frame {
        Json value;
        std::set<std::string> keys;
        std::string pendingKey;
        bool isObject = true;
    };

    bool emit(Json&& value)
    {
        if (finished_) {
            return fail("multiple_root_values");
        }
        if (frames_.empty()) {
            root_ = std::move(value);
            finished_ = true;
            return true;
        }
        Frame& frame = frames_.back();
        if (frame.isObject) {
            if (frame.pendingKey.empty()) {
                return fail("value_without_key");
            }
            frame.value[frame.pendingKey] = std::move(value);
            frame.pendingKey.clear();
        } else {
            if (frame.value.size() >= kMaxArrayLength) {
                return fail("array_too_long");
            }
            frame.value.push_back(std::move(value));
        }
        return true;
    }

    bool finishContainer()
    {
        if (frames_.empty()) {
            return fail("unexpected_container_end");
        }
        Frame frame = std::move(frames_.back());
        frames_.pop_back();
        if (frame.isObject && !frame.pendingKey.empty()) {
            return fail("key_without_value");
        }
        return emit(std::move(frame.value));
    }

    bool fail(const std::string& reason)
    {
        if (!failed_) {
            failed_ = true;
            error_ = reason;
        }
        return false;
    }

    std::vector<Frame> frames_;
    Json root_;
    bool finished_ = false;
    bool failed_ = false;
    std::string error_;
};

}  // namespace

bool ParseStrict(std::string_view text, Json& value, std::string& error)
{
    error.clear();
    if (text.empty()) {
        error = "empty_document";
        return false;
    }
    if (text.size() > kMaxDocumentBytes) {
        error = "document_too_large";
        return false;
    }
    try {
        StrictSaxHandler handler;
        if (!Json::sax_parse(text.begin(), text.end(), &handler)) {
            error = handler.error().empty() ? std::string("invalid_json") : handler.error();
            return false;
        }
        value = handler.root();
        return true;
    } catch (const std::exception& failure) {
        error = std::string("invalid_json: ") + failure.what();
        return false;
    }
}

std::string Dump(const Json& value)
{
    return value.dump(-1, ' ', true, Json::error_handler_t::strict);
}

}  // namespace SessionJson
